import logging
import hashlib
import pickle
import os
from typing import List, Dict, Any, Tuple

from rank_bm25 import BM25Okapi
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SearchOptimizer:
    """
    Hybrid search optimizer.

    BM25 + Dense semantic retrieval kullanır.
    Document embedding cache sayesinde aynı dokümanlar için tekrar tekrar
    embedding üretmez.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._doc_embedding_cache: Dict[str, np.ndarray] = {}
        
        # Cache yapılandırması
        self.cache_dir = "data/cache"
        self.cache_file = os.path.join(self.cache_dir, "embedding_cache.pkl")
        
        try:
            self.model = SentenceTransformer(model_name)
            self._load_cache()
        except Exception as exc:
            logger.exception("Failed to load embedding model %s", model_name)
            raise RuntimeError(f"Embedding model initialization failed: {exc}") from exc

    def _load_cache(self) -> None:
        """Cache dosyasını diskten yükler."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "rb") as f:
                    self._doc_embedding_cache = pickle.load(f)
                logger.info(f"Cache loaded from {self.cache_file}. Size: {len(self._doc_embedding_cache)}")
            except Exception as e:
                logger.warning(f"Could not load cache: {e}. Starting with empty cache.")
                self._doc_embedding_cache = {}

    def _save_cache(self) -> None:
        """Cache'i diske kaydeder."""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.cache_file, "wb") as f:
                pickle.dump(self._doc_embedding_cache, f)
            logger.info(f"Cache saved to {self.cache_file}")
        except Exception as e:
            logger.error(f"Could not save cache: {e}")

    def _preprocess_documents(self, documents: List[str]) -> List[List[str]]:
        return [doc.lower().split() for doc in documents]

    def _get_document_embeddings(self, documents: List[str]) -> np.ndarray:
        """
        Doküman embedding'lerini granüler (doküman bazlı) cache'den getirir.
        Sadece cache'de olmayan dokümanlar için embedding üretir ve batch sonunda kaydeder.
        """
        all_embeddings = [None] * len(documents)
        missing_indices = []
        missing_docs = []

        for i, doc in enumerate(documents):
            # Her doküman için içerik bazlı hash
            doc_hash = hashlib.md5(doc.encode("utf-8")).hexdigest()
            
            if doc_hash in self._doc_embedding_cache:
                all_embeddings[i] = self._doc_embedding_cache[doc_hash]
            else:
                missing_indices.append(i)
                missing_docs.append(doc)

        if missing_docs:
            logger.info(f"Encoding {len(missing_docs)} missing document embeddings...")
            new_embeddings = self.model.encode(
                missing_docs,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            
            for idx, emb in zip(missing_indices, new_embeddings):
                d_hash = hashlib.md5(documents[idx].encode("utf-8")).hexdigest()
                self._doc_embedding_cache[d_hash] = emb
                all_embeddings[idx] = emb
            
            # Batch bittikten sonra diske kaydet
            self._save_cache()

        return np.array(all_embeddings)

    def clear_cache(self) -> None:
        """Embedding cache'i temizler."""
        self._doc_embedding_cache.clear()

    def hybrid_search(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10,
        bm25_weight: float = 0.5,
        dense_weight: float = 0.5,
    ) -> List[Tuple[int, float]]:
        """
        BM25 + Dense skorlarını birleştirerek hybrid search yapar.

        Returns:
            List[(doc_index, combined_score)]
        """
        if not documents:
            return []

        top_k = min(top_k, len(documents))

        # 1. BM25 scoring
        tokenized_docs = self._preprocess_documents(documents)
        bm25 = BM25Okapi(tokenized_docs)
        tokenized_query = query.lower().split()
        bm25_scores = bm25.get_scores(tokenized_query)

        # 2. Dense scoring
        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]

        doc_embeddings = self._get_document_embeddings(documents)
        dense_scores = np.dot(doc_embeddings, query_embedding)

        # 3. Normalize BM25 scores
        bm25_min = np.min(bm25_scores)
        bm25_max = np.max(bm25_scores)

        if bm25_max - bm25_min < 1e-8:
            bm25_scores = np.zeros_like(bm25_scores)
        else:
            bm25_scores = (bm25_scores - bm25_min) / (bm25_max - bm25_min)

        # 4. Dense scores zaten cosine benzeri [-1, 1]
        dense_scores = (dense_scores + 1) / 2

        # 5. Combine
        combined_scores = bm25_weight * bm25_scores + dense_weight * dense_scores

        top_indices = np.argsort(combined_scores)[::-1][:top_k]

        return [(int(idx), float(combined_scores[idx])) for idx in top_indices]

    def rerank_results(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Candidate dict listesini dense similarity ile yeniden sıralar.
        """
        if not candidates:
            return []

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]

        reranked = []

        for candidate in candidates:
            content = candidate.get("content", "")
            if not content:
                continue

            content_embedding = self._get_document_embeddings([content])[0]
            similarity = self._cosine_similarity(query_embedding, content_embedding)

            candidate_copy = candidate.copy()
            candidate_copy["rerank_score"] = float(similarity)
            reranked.append(candidate_copy)

        reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        return reranked[:top_k]

    @staticmethod
    def _cosine_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
        norm_a = np.linalg.norm(vector_a)
        norm_b = np.linalg.norm(vector_b)

        if norm_a <= 0 or norm_b <= 0:
            return 0.0

        return float(np.dot(vector_a, vector_b) / (norm_a * norm_b))