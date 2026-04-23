import logging
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SearchOptimizer:
    """Hybrid search optimizer combining BM25 (sparse) and Dense (semantic) retrieval with reranking."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as exc:
            logger.exception("Failed to load embedding model %s", model_name)
            raise RuntimeError(f"Embedding model initialization failed: {exc}") from exc

    def _preprocess_documents(self, documents: List[str]) -> List[List[str]]:
        """Tokenize documents for BM25."""
        return [doc.lower().split() for doc in documents]

    def hybrid_search(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10,
        bm25_weight: float = 0.5,
        dense_weight: float = 0.5
    ) -> List[Tuple[int, float]]:
        """
        Perform hybrid search combining BM25 and dense retrieval.

        Returns: List of (doc_index, combined_score) tuples, sorted by score descending.
        """
        if not documents:
            return []

        # BM25 scoring
        tokenized_docs = self._preprocess_documents(documents)
        bm25 = BM25Okapi(tokenized_docs)
        tokenized_query = query.lower().split()
        bm25_scores = bm25.get_scores(tokenized_query)

        # Dense scoring
        query_embedding = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
        doc_embeddings = self.model.encode(documents, convert_to_numpy=True, normalize_embeddings=True)
        dense_scores = np.dot(doc_embeddings, query_embedding)

        # Normalize scores to [0, 1]
        bm25_scores = (bm25_scores - np.min(bm25_scores)) / (np.max(bm25_scores) - np.min(bm25_scores) + 1e-8)
        dense_scores = (dense_scores + 1) / 2  # Cosine is [-1, 1], normalize to [0, 1]

        # Combine scores
        combined_scores = bm25_weight * bm25_scores + dense_weight * dense_scores

        # Get top_k results
        top_indices = np.argsort(combined_scores)[::-1][:top_k]
        return [(int(idx), float(combined_scores[idx])) for idx in top_indices]

    def rerank_results(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidate results using cross-encoder or enhanced similarity.

        For now, uses cosine similarity reranking as in VectorDBManager.
        """
        if not candidates:
            return []

        query_embedding = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]

        reranked = []
        for candidate in candidates:
            content = candidate.get("content", "")
            if not content:
                continue

            content_embedding = self.model.encode([content], convert_to_numpy=True, normalize_embeddings=True)[0]
            similarity = self._cosine_similarity(query_embedding, content_embedding)

            candidate_copy = candidate.copy()
            candidate_copy["rerank_score"] = float(similarity)
            reranked.append(candidate_copy)

        # Sort by rerank score descending
        reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        return reranked[:top_k]

    @staticmethod
    def _cosine_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(vector_a)
        norm_b = np.linalg.norm(vector_b)
        if norm_a <= 0 or norm_b <= 0:
            return 0.0
        return float(np.dot(vector_a, vector_b) / (norm_a * norm_b))