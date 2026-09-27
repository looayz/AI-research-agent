import hashlib
import math
from typing import List


class EmbeddingService:
    @staticmethod
    def compute_embedding(text: str, dim: int = 128) -> List[float]:
        """
        Deterministic word-frequency and hash-bag semantic vector generator (dim=128)
        ensuring fast, zero-dependency offline similarity operations across research sessions.
        """
        words = [w.strip() for w in text.lower().split() if len(w.strip()) > 1]
        vector = [0.0] * dim

        if not words:
            return vector

        # Bag-of-words token distribution over feature buckets
        for word in words:
            # Deterministic MD5 hash to avoid Python process-randomized hash seeds
            digest = hashlib.md5(word.encode("utf-8")).hexdigest()
            bucket = int(digest[:8], 16) % dim
            sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
            vector[bucket] += 1.0 * sign

        # L2 Normalize
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        if len(v1) != len(v2) or not v1:
            return 0.0
        return sum(a * b for a, b in zip(v1, v2))
