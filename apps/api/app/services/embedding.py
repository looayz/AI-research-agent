import hashlib
import math
from collections import Counter
from collections.abc import Sequence

from app.core.text import STOPWORDS, tokenize

EMBEDDING_DIM = 256


def _stem(token: str) -> str:
    # Plural folding only (EN/FR): "algorithms" and "algorithm" should match.
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


class EmbeddingService:
    """Offline lexical embeddings (signed feature hashing of unigrams + bigrams).

    No model download and no API key: good at matching sources that share
    vocabulary with the query, not at matching synonyms. Vectors of another
    dimension (e.g. the 128-dim ones of earlier versions) are recomputed
    lazily by the semantic memory service.
    """

    @staticmethod
    def compute_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
        tokens = [_stem(t) for t in tokenize(text) if len(t) > 1 and t not in STOPWORDS and not t.isdigit()]
        vector = [0.0] * dim
        if not tokens:
            return vector

        terms: Counter[str] = Counter(tokens)
        terms.update(f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False))
        for term, tf in terms.items():
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if digest[4] & 1 else -1.0
            weight = 1.0 + math.log(tf)
            if " " in term:
                weight *= 0.5
            vector[bucket] += sign * weight

        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector

    @staticmethod
    def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
        if not v1 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2, strict=True))
        n1 = math.sqrt(sum(a * a for a in v1))
        n2 = math.sqrt(sum(b * b for b in v2))
        return dot / (n1 * n2) if n1 and n2 else 0.0
