import chromadb

from ..config import get_settings
from .embeddings import get_embedder
from .models import Chunk, to_meta
from .chunking import embed_text

COLLECTION = "esolv_kb"
_client = None


def _client_():
    global _client
    if _client is None:
        s = get_settings()
        s.chroma_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(s.chroma_dir))
    return _client


def reset_client():
    global _client
    _client = None


def collection():
    return _client_().get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def rebuild(chunks: list[Chunk]) -> int:
    """Drop and recreate the collection (ingest is idempotent: the docs folder is the source of truth)."""

    emb = get_embedder()
    if chunks:
        emb.embed_query("index readiness")
    try:
        _client_().delete_collection(COLLECTION)
    except Exception:
        pass
    col = collection()
    B = 64
    for i in range(0, len(chunks), B):
        batch = chunks[i:i + B]
        col.add(
            ids=[c.chunk_id for c in batch],
            documents=[c.text for c in batch],
            metadatas=[to_meta(c) for c in batch],
            embeddings=emb.embed_docs([embed_text(c) for c in batch]),
        )
    return len(chunks)


def count() -> int:
    return collection().count()


def all_chunks() -> list[Chunk]:
    res = collection().get(include=["documents", "metadatas"])
    out = []
    for cid, doc, m in zip(res["ids"], res["documents"], res["metadatas"]):
        out.append(chunk_from(cid, doc, m))
    return out


def chunk_from(cid: str, doc: str, m: dict, score: float = 0.0) -> Chunk:
    return Chunk(
        chunk_id=cid, doc_id=m["doc_id"], text=doc, title=m["title"], section=m.get("section", ""),
        page=None if m.get("page", -1) == -1 else m["page"], url=m.get("url", ""), doc_type=m.get("doc_type", ""),
        filename=m.get("filename", ""), score=score,
    )
