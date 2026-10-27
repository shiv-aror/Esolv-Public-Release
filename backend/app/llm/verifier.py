"""Fact-check pass: validates citations, checks numbers against evidence, and has a second model pass compare claims to sources."""
import logging
import re

from . import prompts
from .openrouter import LLMError, OpenRouterClient

log = logging.getLogger(__name__)
_TAG = re.compile(r"\[S(\d+)\]")
_NUM = re.compile(r"(?<![\w\-])\d[\d,\.]*\d|\d")


def strip_invalid_tags(text: str, valid: set[str]) -> str:
    return _TAG.sub(lambda m: m.group(0) if f"S{m.group(1)}" in valid else "", text)


def cited_ids(text: str) -> list[str]:
    seen: list[str] = []
    for m in _TAG.finditer(text):
        sid = f"S{m.group(1)}"
        if sid not in seen:
            seen.append(sid)
    return seen


def ungrounded_numbers(draft: str, haystack: str) -> list[str]:
    """Numbers in the draft that appear nowhere in the evidence or question (a cheap hallucination tripwire)."""
    body = _TAG.sub("", draft)
    body = re.sub(r"(?m)^\s*\d+[.)]\s", "", body)
    body = re.sub(r"(Student|ID-)\s?[A-Z2-7]{4}", "", body)
    known = {n.replace(",", "").rstrip(".") for n in _NUM.findall(haystack)}
    return sorted({n2 for n in _NUM.findall(body) if (n2 := n.replace(",", "").rstrip(".")) not in known})


async def verify(llm: OpenRouterClient, question: str, draft: str, evidence: list[tuple[str, str]], model: str | None = None,
                 images: list[str] | None = None, number_hints: list[str] | None = None) -> dict:
    """evidence: [(source_id, text)]. Returns {status, unsupported_claims, revised_answer}."""
    ev = "\n\n".join(f"[{sid}]\n{txt[:3200]}" for sid, txt in evidence) or "(no evidence)"
    text = f"QUESTION:\n{question}\n\nDRAFT:\n{draft}\n\nEVIDENCE:\n<untrusted_evidence>\n{ev}\n</untrusted_evidence>"
    if number_hints:
        text += f"\n\nHint: these numbers in the draft were not found verbatim in the evidence, so check them carefully: {', '.join(number_hints[:6])}."
    content: str | list = text
    if images:
        text += "\n\nThe teacher attached the image(s) below. Statements that merely describe what is visible in them are supported."
        content = [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": u}} for u in images]
    msgs = [{"role": "system", "content": prompts.VERIFIER}, {"role": "user", "content": content}]
    try:
        out = await llm.chat_json(msgs, model=model)
    except LLMError as e:
        log.warning("verifier failed: %s", e)
        return {"status": "unchecked", "unsupported_claims": [], "revised_answer": None}
    status = out.get("status") if out.get("status") in {"verified", "partial", "unsupported"} else "unchecked"
    claims = out.get("unsupported_claims") or []
    rev = out.get("revised_answer")
    return {"status": status, "unsupported_claims": [str(c) for c in claims][:6] if isinstance(claims, list) else [],
            "revised_answer": rev if isinstance(rev, str) and rev.strip() else None}
