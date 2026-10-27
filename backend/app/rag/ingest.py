"""CLI: python -m app.rag.ingest [docs_dir]  — (re)builds the vector index from data/docs and data/sources.txt."""
import sys
from pathlib import Path

from ..config import get_settings
from . import retriever, store
from .chunking import chunk_document
from .loaders import load_all


def run(docs_dir: Path | None = None) -> dict:
    s = get_settings()
    docs_dir = Path(docs_dir) if docs_dir else s.docs_dir
    docs = load_all(docs_dir, s.data_dir / "sources.txt")
    if not s.canvas_mock:
        docs = [d for d in docs if d.doc_type != "sample"]
    chunks = [c for d in docs for c in chunk_document(d)]

    n = store.rebuild(chunks)
    retriever.invalidate()
    return {"documents": len(docs), "chunks": n, "titles": [d.title for d in docs]}


if __name__ == "__main__":
    stats = run(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(f"Ingested {stats['documents']} documents → {stats['chunks']} chunks")
    for t in stats["titles"]:
        print("  •", t)
