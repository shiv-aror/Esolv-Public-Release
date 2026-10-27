"""Chat orchestration: mask → retrieve (RAG) → tool-calling loop over MCP → draft → fact-check → unmask → cite."""
import json
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

from ..canvas import roster as roster_cache
from ..config import get_settings
from ..guardrails import injection, scope
from ..guardrails.pii import Pseudonymizer
from ..security import sign_path
from . import prompts, verifier
from .openrouter import LLMError, OpenRouterClient
from .toolbox import Toolbox, toolbox_for

Emit = Callable[[dict], Awaitable[None]]

HISTORY_CHAR_BUDGET = 24000


@dataclass
class Source:
    id: str
    title: str
    kind: str
    section: str = ""
    page: int | None = None
    url: str = ""
    filename: str = ""
    text: str = ""
    score: float = 0.0


@dataclass
class RunState:
    sources: list[Source] = field(default_factory=list)
    _keys: dict[tuple, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    def add(self, key: tuple, **kw) -> Source:
        if key in self._keys:
            return next(s for s in self.sources if s.id == self._keys[key])
        s = Source(id=f"S{len(self.sources) + 1}", **kw)
        self.sources.append(s)
        self._keys[key] = s.id
        return s

    def get(self, sid: str) -> Source | None:
        return next((s for s in self.sources if s.id == sid), None)

    def best_knowledge_score(self) -> float:
        return max((s.score for s in self.sources if s.kind == "knowledge"), default=0.0)

    def has_canvas(self) -> bool:
        return any(s.kind == "canvas" for s in self.sources)


def register_result(state: RunState, result: dict) -> dict:
    """Assign [S#] ids to knowledge chunks / canvas sources and neutralize injected text. Mutates + returns result."""
    for ch in result.get("chunks", []) or []:
        clean, flagged = injection.sanitize(ch.get("text", ""))
        if flagged:
            state.flags.append("A retrieved document contained instruction-like text, which was ignored.")
        s = state.add(("k", ch.get("ref")), title=ch.get("title", ""), kind="knowledge", section=ch.get("section", ""),
                      page=ch.get("page"), url=ch.get("url", ""), filename=ch.get("filename", ""), text=clean,
                      score=float(ch.get("score", 0)))
        ch["ref"], ch["cite"], ch["text"] = s.id, f"[{s.id}]", clean
        for k in ("doc_id", "url", "filename"):
            ch.pop(k, None)
    srcs = result.get("sources") or []
    if srcs:
        payload = {k: v for k, v in result.items() if k != "sources"}
        text, flagged = injection.sanitize(json.dumps(payload, ensure_ascii=False))
        if flagged:
            state.flags.append("Canvas content contained instruction-like text, which was ignored.")
        for src in srcs:
            source_text, source_flagged = injection.sanitize(src.get("evidence") or text)
            if source_flagged:
                state.flags.append("Canvas content contained instruction-like text, which was ignored.")
            s = state.add(("c", src.get("title"), src.get("url")), title=src.get("title", "Canvas"), kind="canvas",
                          url=src.get("url", ""), text=source_text)
            src["ref"], src["cite"] = s.id, f"[{s.id}]"
            src.pop("url", None)
            src.pop("evidence", None)
    elif not result.get("chunks") and (result.get("error") or result.get("note") or result.get("matches") == []):

        s = state.add(("n", json.dumps(result, sort_keys=True)), title="Canvas lookup result", kind="canvas",
                      text=json.dumps(result, ensure_ascii=False))
        result["cite"] = f"[{s.id}]"
    return result


def _history(messages: list[dict], pseudo: Pseudonymizer) -> list[dict]:
    out, used = [], 0
    for m in reversed(messages[:-1]):
        if m.get("role") not in {"user", "assistant"}:
            continue
        content = pseudo.mask((m.get("content") or "")[:4000])

        content = re.sub(r"\[S\d+\]", "", content) if m["role"] == "assistant" else content
        used += len(content)
        if used > HISTORY_CHAR_BUDGET:
            out.append({"role": "user", "content": "(Earlier messages in this conversation were omitted for length.)"})
            break
        out.append({"role": m["role"], "content": content})
    return list(reversed(out))


def _evidence_block(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        loc = c["title"] + (f" — {c['section']}" if c.get("section") else "") + (f" (p.{c['page']})" if c.get("page") else "")
        parts.append(f"{c['cite']} {loc}\n{c['text']}")
    return injection.wrap("evidence", "\n\n".join(parts)) if parts else ""


def _citation(s: Source, pseudo: Pseudonymizer) -> dict:
    url = s.url or (sign_path(f"/sources/file/{s.filename}", 3600 * 8) if s.filename else "")
    if url.startswith("/"):
        url = get_settings().public_url.rstrip("/") + url
    if s.page and urlsplit(url).path.lower().endswith(".pdf"):
        parts = urlsplit(url)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, f"page={s.page}"))
    return {"id": s.id, "title": pseudo.unmask(s.title), "section": s.section, "page": s.page, "url": url,
            "kind": s.kind, "snippet": "" if s.kind == "canvas" else pseudo.unmask(s.text[:260].replace("\n", " "))}


def _source_preview(state: RunState, pseudo: Pseudonymizer, ids: list[str] | None = None) -> list[dict]:
    """Linkable source locations shown while retrieval and verification are running."""
    selected = [state.get(i) for i in ids] if ids is not None else state.sources
    seen: set[tuple[str, int | None, str]] = set()
    out = []
    for source in selected:
        if not source:
            continue
        citation = _citation(source, pseudo)
        key = (citation["url"] or citation["title"], citation["page"], citation["section"])
        if key in seen:
            continue
        seen.add(key)
        out.append(citation)
    return out


async def _finish_draft(llm: OpenRouterClient, convo: list[dict], first: dict) -> str:
    """Complete a length-limited draft before it reaches the fact checker or UI."""
    parts = [first["content"]]
    base_convo = convo
    out = first
    for _ in range(2):
        if out.get("finish_reason") != "length":
            return "".join(parts)
        if not parts[-1]:
            raise LLMError("The model ran out of output space before answering.")
        continuation = [*base_convo, {"role": "assistant", "content": "".join(parts)},
                        {"role": "user", "content": "Continue exactly where your answer stopped. Do not repeat text. Finish the remaining requested guidance and citations."}]
        out = await llm.chat(continuation, max_tokens=2200)
        parts.append(out["content"])
    if out.get("finish_reason") == "length":
        raise LLMError("The model could not finish its answer within the output limit.")
    return "".join(parts)


def _wants_upcoming_assignments(question: str) -> bool:
    q = question.lower()
    return (bool(re.search(r"\bassignments?\b", q))
            and bool(re.search(r"\b(upcoming|coming up|due|next)\b", q))
            and bool(re.search(r"\b(?:my|all)\s+(?:canvas\s+)?courses\b|\bcanvas\s+courses\b", q)))


def _demo_student_id(question: str) -> str | None:
    if not re.search(r"\b(?:demo|sample|synthetic|fictional)\b", question, re.I):
        return None
    match = re.search(r"(?<!\d)\d{6,9}(?!\d)", question)
    return match.group(0) if match else None


async def run_chat(
    user_email: str, messages: list[dict], page_context: dict | None, images: list[str], emit: Emit,
    llm: OpenRouterClient | None = None, toolbox_cm: Toolbox | None = None, files: list[dict] | None = None,
) -> dict:
    own_llm = llm is None
    llm = llm or OpenRouterClient()
    try:
        return await _run_chat(user_email, messages, page_context, images, emit, llm, toolbox_cm, files or [])
    finally:
        if own_llm:
            await llm.aclose()


async def _run_chat(user_email, messages, page_context, images, emit, llm, toolbox_cm, files) -> dict:
    s = get_settings()
    question = (messages[-1].get("content") or "").strip()
    if scope.is_greeting(question) and not images and not files:
        return {"answer": scope.GREETING_REPLY, "citations": [], "verification": {"status": "n/a", "notes": []}, "flags": []}

    state = RunState()
    pseudo = Pseudonymizer(user_email)
    pseudo.register_roster(await roster_cache.get_roster(user_email))

    safety_prefix = scope.SAFETY_REPLY + "\n\n" if scope.is_safety_concern(question) else ""
    masked_q = pseudo.mask(question)


    file_srcs = []
    for f in files:
        text, flagged = injection.sanitize(pseudo.mask(f.get("text", "")))
        if flagged:
            state.flags.append("An attached file contained instruction-like text, which was ignored.")
        file_srcs.append((state.add(("f", f.get("name")), title=f"Attached: {f.get('name', 'file')}", kind="file", text=text), text, pseudo.mask(f.get("name", "file"))))

    box = toolbox_cm or toolbox_for(user_email)
    async with box as tools:
        await emit({"type": "status", "text": "Searching MCPS policies and instruction…"})
        prev_users = [m["content"] for m in messages[:-1] if m.get("role") == "user"]
        rq = masked_q if len(masked_q.split()) >= 6 or not prev_users else f"{pseudo.mask(prev_users[-1])} {masked_q}"
        pre = register_result(state, await tools.call("search_mcps_knowledge", {"query": rq[:500]}))
        demo = None
        if demo_id := _demo_student_id(question):
            await emit({"type": "status", "text": "Reading the fictional demo student record…"})
            raw_demo = await tools.call("get_demo_student", {"sis_id": demo_id})
            pseudo.register_from_obj(raw_demo)
            demo = register_result(state, pseudo.mask_obj(raw_demo)) if raw_demo.get("chunks") else raw_demo
        upcoming = None
        if _wants_upcoming_assignments(question):
            await emit({"type": "status", "text": "Checking upcoming assignments across your Canvas courses…"})
            upcoming = register_result(state, await tools.call("list_upcoming_assignments", {}))
        await emit({"type": "sources", "text": "Retrieved sources", "stage": "retrieved",
                    "sources": _source_preview(state, pseudo)})
        await emit({"type": "status", "text": "Reading the matching passages…" if pre.get("chunks") else "Checking available sources…"})

        user_text = f"{masked_q}"
        ev = _evidence_block(pre.get("chunks", []))
        if ev:
            user_text += f"\n\nRetrieved MCPS sources for this question:\n{ev}"
        if demo is not None:
            demo_ev = _evidence_block(demo.get("chunks", []))
            user_text += ("\n\nFictional demo student record (never treat it as a real student plan):\n" + demo_ev
                          if demo_ev else f"\n\nSynthetic demo lookup: {demo.get('message', 'No record found.')}")
        if upcoming is not None:
            user_text += "\n\nCurrent Canvas upcoming assignments (already checked; use these results):\n" + injection.wrap(
                "canvas_data", json.dumps(upcoming, ensure_ascii=False))
        if page_context and (page_context.get("selection") or page_context.get("title")):
            pc = f"Page title: {page_context.get('title', '')}\nURL: {page_context.get('url', '')}\nSelected text: {page_context.get('selection', '')}"
            user_text += "\n\nThe teacher is looking at this web page (context only):\n" + injection.wrap("page_context", pseudo.mask(pc))
        for src, text, mname in file_srcs:
            user_text += f"\n\nThe teacher attached the file \"{mname}\" ({src.id}). Its text:\n<untrusted_attachment>\n{text}\n</untrusted_attachment>"
        content: list | str = user_text
        if images:
            content = [{"type": "text", "text": user_text}] + [{"type": "image_url", "image_url": {"url": u}} for u in images]
        convo = [{"role": "system", "content": prompts.SYSTEM}, *_history(messages, pseudo), {"role": "user", "content": content}]

        draft = ""
        defs = tools.openai_tools()
        for step in range(s.max_tool_steps):
            out = await llm.chat(convo, tools=defs, max_tokens=2200)
            if not out["tool_calls"]:
                draft = await _finish_draft(llm, convo, out)
                break
            convo.append({"role": "assistant", "content": out["content"] or None, "tool_calls": out["tool_calls"]})
            for tc in out["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                await emit({"type": "status", "text": _status_for(name)})
                real_args = pseudo.unmask_obj(args)
                res = await tools.call(name, real_args)
                pseudo.register_from_obj(res)
                res = register_result(state, pseudo.mask_obj(res))
                await emit({"type": "sources", "text": "Retrieved sources", "stage": "retrieved",
                            "sources": _source_preview(state, pseudo)})
                convo.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(res, ensure_ascii=False)[:14000]})
        else:
            convo.append({"role": "user", "content": "Write your final answer now using only what you have gathered."})
            draft = await _finish_draft(llm, convo, await llm.chat(convo, max_tokens=2200))


    cited = verifier.cited_ids(draft)
    if (not images and not file_srcs and not cited and state.best_knowledge_score() < s.min_relevance and not state.has_canvas()):
        near = [x for x in state.sources if x.kind == "knowledge" and x.score >= 0.25][:3]
        return {"answer": safety_prefix + scope.NOT_FOUND_REPLY,
                "citations": [_citation(x, pseudo) for x in near], "verification": {"status": "not_found", "notes": []},
                "flags": state.flags}


    await emit({"type": "status", "text": "Checking each claim against the source passages…"})
    valid = {x.id for x in state.sources}
    draft = verifier.strip_invalid_tags(draft, valid)
    cited = verifier.cited_ids(draft)
    notes: list[str] = []
    status, rounds = "unchecked", 0
    while True:

        ev_ids = list(dict.fromkeys(
            cited + [x.id for x in sorted(state.sources, key=lambda x: -x.score)[:6]]
            + [x.id for x in state.sources if x.kind in {"file", "canvas"}]))
        await emit({"type": "sources", "text": "Sources used for fact checking", "stage": "checking",
                    "sources": _source_preview(state, pseudo, ev_ids)})
        ev_pairs = [(x.id, x.text) for i in ev_ids if (x := state.get(i))]
        hay = " ".join(t for _, t in ev_pairs) + " " + masked_q
        bad_nums = [] if images else verifier.ungrounded_numbers(draft, hay)
        v = await verifier.verify(llm, masked_q, draft, ev_pairs, images=images, number_hints=bad_nums)
        status = v["status"]
        if status in {"partial", "unsupported"} and v["revised_answer"] and rounds < 2:

            notes += [f"Removed or softened: {c}" for c in v["unsupported_claims"][:3]]
            draft = verifier.strip_invalid_tags(v["revised_answer"], valid)
            cited = verifier.cited_ids(draft)
            rounds += 1
            await emit({"type": "status", "text": "Double-checking the corrected answer…"})
            continue
        break
    if status == "verified":
        notes = []


    answer = safety_prefix + pseudo.unmask(draft.strip())
    if scope.needs_coordinator_note(question):
        answer += scope.COORDINATOR_NOTE
    used = verifier.cited_ids(answer)
    citations = [_citation(x, pseudo) for i in used if (x := state.get(i))]
    return {"answer": answer, "citations": citations,
            "verification": {"status": status, "notes": [pseudo.unmask(n) for n in notes]},
            "flags": sorted(set(state.flags)), "usage": {}}


def _status_for(tool: str) -> str:
    return {
        "search_mcps_knowledge": "Searching MCPS materials…",
        "get_document_section": "Reading a document section…",
        "list_sources": "Listing sources…",
        "find_student": "Looking up the student in your Canvas courses…",
        "get_student_profile": "Checking the student's roster profile…",
        "get_accommodations": "Checking recorded accommodations…",
        "list_my_courses": "Reading your Canvas courses…",
        "list_assignments": "Reading Canvas assignments…",
        "list_upcoming_assignments": "Checking upcoming assignments across your Canvas courses…",
        "get_demo_student": "Reading the fictional demo student record…",
        "get_course_page": "Reading a Canvas page…",
    }.get(tool, "Working…")
