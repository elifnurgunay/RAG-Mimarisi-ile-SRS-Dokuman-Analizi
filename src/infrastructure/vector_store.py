# src/infrastructure/vector_store.py

from langchain_qdrant import QdrantVectorStore

from src.config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME


class VectorStoreService:
    def __init__(self, embeddings, collection_name: str = QDRANT_COLLECTION_NAME):
        self.embeddings = embeddings
        self.collection_name = collection_name
        self.vector_store = None

    def create_from_documents(self, documents, force_recreate: bool = True):
        self.vector_store = QdrantVectorStore.from_documents(
            documents,
            self.embeddings,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            collection_name=self.collection_name,
            force_recreate=force_recreate,
            prefer_grpc=False,
        )
        return self.vector_store

    def connect_existing(self):
        self.vector_store = QdrantVectorStore.from_existing_collection(
            embedding=self.embeddings,
            collection_name=self.collection_name,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            prefer_grpc=False,
        )
        return self.vector_store

    def get_store(self):
        if self.vector_store is None:
            return self.connect_existing()
        return self.vector_store
        
    def similarity_search_with_score(self, query: str, k: int = 5):
    store = self.get_store()
    return store.similarity_search_with_score(query, k=k)