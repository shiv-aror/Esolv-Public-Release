"""Hybrid retrieval: vector (Chroma) + BM25 → Reciprocal Rank Fusion → optional cross-encoder rerank."""
import math
import re
import threading

from rank_bm25 import BM25Okapi

from ..config import get_settings
from . import store
from .embeddings import get_embedder
from .models import Chunk

_lock = threading.Lock()
_bm25 = None
_bm25_chunks: list[Chunk] = []
_bm25_count = -1


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _tok(t: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", t.lower())]


def invalidate():
    global _bm25_count
    _bm25_count = -1


def _ensure_bm25():
    global _bm25, _bm25_chunks, _bm25_count
    n = store.count()
    if n == _bm25_count and _bm25 is not None:
        return
    with _lock:
        _bm25_chunks = store.all_chunks()
        _bm25 = BM25Okapi([_tok(f"{c.title} {c.section} {c.text}") for c in _bm25_chunks]) if _bm25_chunks else None
        _bm25_count = n


def _cos(a: list[float], b: list[float]) -> float:
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (da * db)


def _rerank(query: str, chunks: list[Chunk]) -> list[Chunk]:
    s = get_settings()
    if not s.rerank or len(chunks) < 2:
        return chunks
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        enc = TextCrossEncoder(model_name=s.rerank_model, cache_dir=str(s.models_dir))
        scores = list(enc.rerank(query, [c.text for c in chunks]))
        return [c for _, c in sorted(zip(scores, chunks), key=lambda x: -x[0])]
    except Exception:
        return chunks


def search(query: str, doc_type: str | None = None, top_k: int | None = None) -> list[Chunk]:
    s = get_settings()
    top_k = top_k or s.top_k
    if store.count() == 0 or not query.strip():
        return []
    _ensure_bm25()
    col = store.collection()
    qv = get_embedder().embed_query(query)

    where = {"doc_type": doc_type} if doc_type else None
    vres = col.query(query_embeddings=[qv], n_results=min(40, store.count()), where=where,
                     include=["documents", "metadatas", "distances"])
    vec_ids = vres["ids"][0]
    by_id: dict[str, Chunk] = {}
    for cid, doc, m, dist in zip(vec_ids, vres["documents"][0], vres["metadatas"][0], vres["distances"][0]):
        by_id[cid] = store.chunk_from(cid, doc, m, score=max(0.0, 1.0 - dist))

    bm_ids: list[str] = []
    if _bm25 is not None:
        scores = _bm25.get_scores(_tok(query))
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
        for i in ranked[:40]:
            c = _bm25_chunks[i]
            if scores[i] <= 0 or (doc_type and c.doc_type != doc_type):
                continue
            bm_ids.append(c.chunk_id)
            by_id.setdefault(c.chunk_id, c)


    fused: dict[str, float] = {}
    for ranking in (vec_ids, bm_ids):
        for rank, cid in enumerate(ranking):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (60 + rank)
    report_query = doc_type == "research" or bool(re.search(r"\b(cal|evaluation|report|research|study)\b", query.lower()))
    query_terms = set(_tok(query))

    def rank(cid: str) -> float:
        chunk = by_id[cid]
        title_overlap = len(query_terms.intersection(_tok(chunk.title))) / max(1, len(query_terms))
        current_source_bonus = 0.02 if chunk.doc_type != "research" and not report_query else 0.0
        return fused[cid] + 0.06 * title_overlap + current_source_bonus

    order = sorted(fused, key=lambda cid: -rank(cid))[: max(top_k * 5, 20)]


    missing = [c for c in order if by_id[c].score == 0.0]
    if missing:
        got = col.get(ids=missing, include=["embeddings"])
        for cid, e in zip(got["ids"], got["embeddings"]):
            by_id[cid].score = max(0.0, _cos(qv, [float(x) for x in e]))

    cands = _rerank(query, [by_id[c] for c in order])

    seen, per_doc, out = set(), {}, []
    for c in cands:
        key = re.sub(r"\W+", "", c.text.lower())[:200]
        if key in seen:
            continue
        if not report_query and per_doc.get(c.doc_id, 0) >= (1 if c.doc_type == "research" else 2):
            continue
        seen.add(key)
        per_doc[c.doc_id] = per_doc.get(c.doc_id, 0) + 1
        out.append(c)
        if len(out) >= top_k:
            break
    return out


def best_relevance(chunks: list[Chunk]) -> float:
    return max((c.score for c in chunks), default=0.0)
