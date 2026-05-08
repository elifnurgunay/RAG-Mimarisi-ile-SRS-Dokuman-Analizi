import uuid
from typing import List

from langchain_core.documents import Document
from qdrant_client import QdrantClient, models

from src.config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME
from src.infrastructure.embedding_service import EmbeddingService
from src.infrastructure.sparse_embedding_service import SparseEmbeddingService


class HybridQdrantStore:
    def __init__(
        self,
        collection_name: str = QDRANT_COLLECTION_NAME,
        dense_vector_name: str = "dense",
        sparse_vector_name: str = "sparse",
    ):
        self.collection_name = collection_name
        self.dense_vector_name = dense_vector_name
        self.sparse_vector_name = sparse_vector_name

        self.client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )

        self.embedding_service = EmbeddingService()
        self.dense_embeddings = self.embedding_service.get_embeddings()
        self.sparse_embeddings = SparseEmbeddingService()

    def recreate_collection(self, vector_size: int) -> None:
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config={
                self.dense_vector_name: models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                self.sparse_vector_name: models.SparseVectorParams()
            },
        )

    def add_documents(self, documents: List[Document], force_recreate: bool = True) -> None:
        if not documents:
            return

        texts = [doc.page_content for doc in documents]

        dense_vectors = self.dense_embeddings.embed_documents(texts)
        sparse_vectors = [self.sparse_embeddings.encode(text) for text in texts]

        vector_size = len(dense_vectors[0])

        if force_recreate:
            self.recreate_collection(vector_size=vector_size)

        points = []

        for doc, dense_vector, sparse_vector in zip(documents, dense_vectors, sparse_vectors):
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector={
                        self.dense_vector_name: dense_vector,
                        self.sparse_vector_name: sparse_vector,
                    },
                    payload={
                        "page_content": doc.page_content,
                        "metadata": doc.metadata,
                    },
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def hybrid_search(self, query: str, top_k: int = 5) -> List[Document]:
        dense_query = self.dense_embeddings.embed_query(query)
        sparse_query = self.sparse_embeddings.encode(query)

        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_query,
                    using=self.dense_vector_name,
                    limit=top_k * 4,
                ),
                models.Prefetch(
                    query=sparse_query,
                    using=self.sparse_vector_name,
                    limit=top_k * 4,
                ),
            ],
            query=models.FusionQuery(
                fusion=models.Fusion.RRF,
            ),
            limit=top_k,
            with_payload=True,
        )

        docs: List[Document] = []

        for point in response.points:
            payload = point.payload or {}
            metadata = payload.get("metadata", {})
            metadata["qdrant_score"] = float(point.score)

            docs.append(
                Document(
                    page_content=payload.get("page_content", ""),
                    metadata=metadata,
                )
            )

        return docs

    def scroll_all_documents(self, limit: int = 100) -> List[Document]:
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            with_payload=True,
        )

        docs = []

        for point in points:
            payload = point.payload or {}
            docs.append(
                Document(
                    page_content=payload.get("page_content", ""),
                    metadata=payload.get("metadata", {}),
                )
            )

        return docs