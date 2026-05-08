from collections import Counter
from typing import Dict, List

import numpy as np
from qdrant_client.models import SparseVector


class SparseEmbeddingService:
    """
    Basit lexical sparse vector üretici.

    Production için SPLADE/BM25 tabanlı sparse encoder daha doğru olur.
    Bu MVP sürümü token hash + term frequency kullanır.
    """

    def __init__(self, vocab_size: int = 30000):
        self.vocab_size = vocab_size

    def encode(self, text: str) -> SparseVector:
        tokens = self._tokenize(text)
        counts = Counter(tokens)

        indices: List[int] = []
        values: List[float] = []

        for token, count in counts.items():
            index = abs(hash(token)) % self.vocab_size
            indices.append(index)
            values.append(float(count))

        if not indices:
            return SparseVector(indices=[], values=[])

        norm = np.linalg.norm(values)
        if norm > 0:
            values = [v / norm for v in values]

        return SparseVector(indices=indices, values=values)

    def _tokenize(self, text: str) -> List[str]:
        return [
            token.strip(".,:;!?()[]{}\"'").lower()
            for token in text.split()
            if token.strip()
        ]