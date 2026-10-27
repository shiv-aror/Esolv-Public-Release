import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from ..config import get_settings


class Embedder(Protocol):
    def embed_docs(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder. Offline; used for tests and as a no-download fallback."""
    dim = 384
    _stop = {"the", "a", "an", "of", "to", "and", "in", "is", "for", "on", "what", "how", "do", "i", "my", "are", "with"}

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        toks = [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in self._stop]
        for t in toks:
            stem = t[:-1] if t.endswith("s") and len(t) > 3 else t
            h = int(hashlib.md5(stem.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_docs(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class FastEmbedEmbedder:
    def __init__(self):
        from fastembed import TextEmbedding
        s = get_settings()
        s.models_dir.mkdir(parents=True, exist_ok=True)
        self.model = TextEmbedding(model_name=s.embedding_model, cache_dir=str(s.models_dir))

    def embed_docs(self, texts):
        return [list(map(float, v)) for v in self.model.embed(texts)]

    def embed_query(self, text):
        return [float(x) for x in next(iter(self.model.query_embed(text)))]


@lru_cache
def get_embedder() -> Embedder:
    if get_settings().embeddings == "hash":
        return HashEmbedder()
    return FastEmbedEmbedder()
