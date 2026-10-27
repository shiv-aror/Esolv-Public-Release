"""Heading-aware chunking: ~800 tokens (≈3200 chars) with ~12% overlap, never crossing a section."""
import re

from .models import Chunk, Document

MAX_CHARS = 3200
OVERLAP = 400


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    paras = re.split(r"\n\s*\n|\n(?=[-*•]|\d+\.)", text)
    out, cur = [], ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 2 <= MAX_CHARS:
            cur = f"{cur}\n\n{p}" if cur else p
            continue
        if cur:
            out.append(cur)
            tail = cur[-OVERLAP:]
            cur = tail[tail.find(" ") + 1:] if " " in tail else tail
        while len(p) > MAX_CHARS:
            out.append(p[:MAX_CHARS])
            p = p[MAX_CHARS - OVERLAP:]
        cur = f"{cur}\n\n{p}" if cur else p
    if cur.strip():
        out.append(cur)
    return out


def chunk_document(doc: Document) -> list[Chunk]:
    chunks: list[Chunk] = []
    for si, sec in enumerate(doc.sections):
        for pi, piece in enumerate(_split_long(sec.text)):
            if len(piece.strip()) < 40:
                continue
            chunks.append(Chunk(
                chunk_id=f"{doc.doc_id}-{si}-{pi}", doc_id=doc.doc_id, text=piece.strip(), title=doc.title,
                section=sec.heading, page=sec.page, url=doc.url, doc_type=doc.doc_type, filename=doc.filename,
            ))
    return chunks


def embed_text(c: Chunk) -> str:
    """Text actually embedded: heading context improves retrieval of short sections."""
    head = f"{c.title} — {c.section}" if c.section else c.title
    return f"{head}\n{c.text}"
