"""Knowledge MCP server: RAG over vetted MCPS documents (ELD paperwork, accountability, instructional materials)."""
import csv

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from ..config import get_settings
from ..db import audit
from ..rag import retriever, store
from .context import require_user

mcp = FastMCP(
    "esolv-knowledge",
    instructions="Search the curated MCPS knowledge base. Always cite the returned source for any fact you use.",
    stateless_http=True, json_response=True, streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def chunk_dict(c) -> dict:
    return {"ref": c.chunk_id, "doc_id": c.doc_id, "title": c.title, "section": c.section, "page": c.page,
            "url": c.url, "filename": c.filename, "doc_type": c.doc_type, "score": round(c.score, 3), "text": c.text}


def include_policy_continuations(chunks: list) -> list:
    """Keep the next PDF page when a retrieved policy page ends mid-sentence."""
    if not chunks:
        return chunks
    by_page = {(c.doc_id, c.page): c for c in store.all_chunks() if c.doc_type == "policy" and c.page}
    out, seen = [], set()
    for c in chunks:
        if c.chunk_id not in seen:
            out.append(c)
            seen.add(c.chunk_id)
        if c.doc_type != "policy" or not c.page or c.text.rstrip().endswith((".", "!", "?")):
            continue
        following = by_page.get((c.doc_id, c.page + 1))
        if following and following.chunk_id not in seen:
            following.score = c.score * 0.95
            out.append(following)
            seen.add(following.chunk_id)
    return out


@mcp.tool()
def search_mcps_knowledge(query: str, doc_type: str | None = None, top_k: int = 6) -> dict:
    """Search MCPS instructional materials and ELD paperwork/accountability documents. doc_type may be: guidance, form, accountability, instructional, policy."""
    audit(require_user(), "tool.search_mcps_knowledge")
    chunks = include_policy_continuations(retriever.search(query, doc_type=doc_type, top_k=max(1, min(top_k, 10))))
    return {"chunks": [chunk_dict(c) for c in chunks], "relevance": round(retriever.best_relevance(chunks), 3)}


@mcp.tool()
def get_demo_student(sis_id: str) -> dict:
    """Read a fictional student and accommodations from the synthetic demo CSVs only. Use only when the teacher explicitly asks about a demo, sample, or synthetic student."""
    audit(require_user(), "tool.get_demo_student")
    data_dir = get_settings().data_dir
    with (data_dir / "synthetic-students.csv").open(newline="") as f:
        student = next((row for row in csv.DictReader(f) if row["sis_id"] == sis_id), None)
    if student is None:
        return {"student": None, "message": "No fictional demo student has that ID."}
    with (data_dir / "accommodations.sample.csv").open(newline="") as f:
        record = next((row for row in csv.DictReader(f) if row["sis_id"] == sis_id), None)
    accommodations = [a.strip() for a in (record or student)["accommodations"].split(";") if a.strip()]
    text = (f"SYNTHETIC DEMO ONLY. Fictional student {student['student_name']} (ID {sis_id}), grade {student['grade']}, "
            f"ELD level {student['eld_level']}. Sample accommodations: {', '.join(accommodations)}. "
            f"Sample plan review date: {student['plan_review_date']}. This is not an approved student plan.")
    return {"student": {"name": student["student_name"], "sis_id": sis_id},
            "chunks": [{"ref": f"demo-{sis_id}", "doc_id": "synthetic-demo-students", "title": "Synthetic demo student record",
                        "section": "Fictional accommodations", "page": None, "url": "", "filename": "",
                        "doc_type": "sample", "score": 1.0, "text": text}]}


@mcp.tool()
def get_document_section(doc_id: str, section_contains: str = "") -> dict:
    """Return all chunks of one document, optionally only those whose section heading contains the given text."""
    require_user()
    out = [c for c in store.all_chunks() if c.doc_id == doc_id and section_contains.lower() in c.section.lower()]
    return {"chunks": [chunk_dict(c) for c in out[:12]]}


@mcp.tool()
def list_sources() -> dict:
    """List every document in the knowledge base."""
    require_user()
    docs: dict[str, dict] = {}
    for c in store.all_chunks():
        docs.setdefault(c.doc_id, {"doc_id": c.doc_id, "title": c.title, "doc_type": c.doc_type, "url": c.url})
    return {"documents": sorted(docs.values(), key=lambda d: d["title"])}
