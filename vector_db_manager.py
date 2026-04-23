import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

load_dotenv()
logger = logging.getLogger(__name__)


class VectorDBManager:
    """Manage embeddings and Qdrant storage for SRS requirement records with CRUD operations."""

    def __init__(
        self,
        collection_name: str = "srs_requirements",
        url_env: str = "QDRANT_URL",
        api_key_env: str = "QDRANT_API_KEY",
    ) -> None:
        self.collection_name = collection_name
        self.url = os.getenv(url_env)
        self.api_key = os.getenv(api_key_env)
        self.model_name = "all-MiniLM-L6-v2"

        if not self.url or not self.api_key:
            raise EnvironmentError(
                f"Environment variables {url_env} and {api_key_env} must be set."
            )

        try:
            self.model = SentenceTransformer(self.model_name)
        except Exception as exc:
            logger.exception("Failed to load embedding model %s", self.model_name)
            raise RuntimeError(
                f"Embedding model initialization failed: {exc}"
            ) from exc

        try:
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                prefer_grpc=False,
            )
            self._ensure_collection()
        except Exception as exc:
            logger.exception("Failed to connect to Qdrant at %s", self.url)
            raise ConnectionError(
                f"Qdrant connection failed: {exc}"
            ) from exc

    def _ensure_collection(self) -> None:
        """Create the collection if it does not exist."""
        try:
            collections = self.client.get_collections().collections
            if self.collection_name not in {c.name for c in collections}:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors=VectorParams(size=384, distance=Distance.COSINE),
                )
        except Exception as exc:
            logger.exception("Failed to ensure Qdrant collection %s", self.collection_name)
            raise RuntimeError(
                f"Could not create or verify collection {self.collection_name}: {exc}"
            ) from exc

    def health_check(self) -> bool:
        """Return True if Qdrant connection and collection access are healthy."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            logger.exception("Health check failed for Qdrant connection")
            return False

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of text strings into numeric vectors."""
        if not texts:
            return []

        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vectors.tolist()

    def create_records(self, records: List[Dict[str, Any]]) -> None:
        """Create new requirement records in Qdrant."""
        if not records:
            return

        try:
            texts = [record["content"] for record in records]
            vectors = self._embed_texts(texts)
            points = []

            for record, vector in zip(records, vectors):
                if "req_id" not in record or "content" not in record:
                    raise ValueError("Each record must include 'req_id' and 'content'.")

                payload = {
                    "req_id": record["req_id"],
                    "content": record["content"],
                    "page_no": record.get("page_no"),
                    "type": record.get("type"),
                }

                points.append(
                    PointStruct(
                        id=str(record["req_id"]),
                        vector=vector,
                        payload=payload,
                    )
                )

            self.client.upsert(collection_name=self.collection_name, points=points)
        except Exception as exc:
            logger.exception("Failed to create records in Qdrant")
            raise RuntimeError("create_records failed") from exc

    def read_records(self, query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Read/search closest requirement records for the given query."""
        if not query_text:
            return []

        try:
            query_vector = self._embed_texts([query_text])[0]
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
                with_vector=True,
            )
            return self._rerank_results(query_vector, results)
        except Exception as exc:
            logger.exception("Failed to search Qdrant for query: %s", query_text)
            raise RuntimeError("read_records failed") from exc

    def update_record(self, req_id: str, updated_content: str, page_no: Optional[int] = None, req_type: Optional[str] = None) -> None:
        """Update an existing record by req_id."""
        try:
            # Generate new vector for updated content
            vector = self._embed_texts([updated_content])[0]

            payload = {
                "req_id": req_id,
                "content": updated_content,
                "page_no": page_no,
                "type": req_type,
            }

            point = PointStruct(
                id=req_id,
                vector=vector,
                payload=payload,
            )

            self.client.upsert(collection_name=self.collection_name, points=[point])
        except Exception as exc:
            logger.exception("Failed to update record %s", req_id)
            raise RuntimeError("update_record failed") from exc

    def delete_record(self, req_id: str) -> None:
        """Delete a record by req_id."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector={"ids": [req_id]}
            )
        except Exception as exc:
            logger.exception("Failed to delete record %s", req_id)
            raise RuntimeError("delete_record failed") from exc

    def _rerank_results(self, query_vector: List[float], results: List[Any]) -> List[Dict[str, Any]]:
        """Refine search results with cosine similarity reranker."""
        import numpy as np

        query_np = np.array(query_vector, dtype=np.float32)
        reranked: List[Dict[str, Any]] = []

        for item in results:
            payload = getattr(item, "payload", {}) or {}
            vector = getattr(item, "vector", None)
            base_score = getattr(item, "score", None)
            rerank_score = base_score if vector is None else self._cosine_similarity(query_np, np.array(vector, dtype=np.float32))

            reranked.append(
                {
                    "req_id": payload.get("req_id"),
                    "content": payload.get("content"),
                    "page_no": payload.get("page_no"),
                    "type": payload.get("type"),
                    "qdrant_score": float(base_score) if base_score is not None else None,
                    "rerank_score": float(rerank_score) if rerank_score is not None else None,
                    "payload": payload,
                }
            )

        reranked.sort(key=lambda item: item["rerank_score"] or 0.0, reverse=True)
        return reranked

    @staticmethod
    def _cosine_similarity(vector_a: 'np.ndarray', vector_b: 'np.ndarray') -> float:
        """Compute cosine similarity between two vectors."""
        import numpy as np
        norm_a = np.linalg.norm(vector_a)
        norm_b = np.linalg.norm(vector_b)
        if norm_a <= 0 or norm_b <= 0:
            return 0.0
        return float(np.dot(vector_a, vector_b) / (norm_a * norm_b))