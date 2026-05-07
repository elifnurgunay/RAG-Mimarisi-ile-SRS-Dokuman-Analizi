# src/infrastructure/retrieval_service.py

import os

from src.parsing.chunking_strategy import ReqChunkingStrategy
from src.infrastructure.pdf_loader import PDFLoaderService
from src.infrastructure.embedding_service import EmbeddingService
from src.infrastructure.vector_store import VectorStoreService
from src.infrastructure.search_optimization import SearchOptimizer
from src.config import QDRANT_COLLECTION_NAME, REQUIREMENT_ID_PATTERN


class RetrievalService:
    def __init__(self, collection_name: str = QDRANT_COLLECTION_NAME):
        self.collection_name = collection_name

        self.pdf_loader = PDFLoaderService()
        self.embedding_service = EmbeddingService()
        self.embeddings = self.embedding_service.get_embeddings()

        self.vector_service = VectorStoreService(
            embeddings=self.embeddings,
            collection_name=self.collection_name,
        )

        self.optimizer = SearchOptimizer()
        self.chunk_strategy = ReqChunkingStrategy(
            req_pattern=REQUIREMENT_ID_PATTERN,
            fallback_chunk_size=500,
            fallback_overlap=50,
        )

    def load_and_index_pdf(self, pdf_path: str) -> bool:
        if not os.path.exists(pdf_path):
            print(f"Hata: {pdf_path} dosyası bulunamadı!")
            return False

        documents = self.pdf_loader.load(pdf_path)
        chunks = self.chunk_strategy.chunk_documents(documents)

        chunks = [
            doc for doc in chunks
            if doc.page_content and doc.page_content.strip()
        ]

        if not chunks:
            print("Uyarı: Indexlenecek geçerli metin bulunamadı!")
            return False

        self.vector_service.create_from_documents(chunks, force_recreate=True)
        print(f"Indexleme tamamlandı. Chunk sayısı: {len(chunks)}")
        return True

    def add_structured_data(self, requirements_json: list):
        try:
            from langchain_core.documents import Document
        except ImportError:
            from langchain.schema import Document

        docs = [
            Document(
                page_content=req["text"],
                metadata={"req_id": req["id"]}
            )
            for req in requirements_json
            if req.get("text")
        ]

        if not docs:
            return False

        store = self.vector_service.get_store()
        store.add_documents(docs)
        return True

    def get_all_documents(self, k: int = 100):
        store = self.vector_service.get_store()
        return store.similarity_search("", k=k)

    def get_similar_requirements(self, query: str, top_k: int = 3):
        store = self.vector_service.get_store()

        candidates = store.similarity_search(query, k=top_k * 4)

        if not candidates:
            return []

        candidate_texts = [doc.page_content for doc in candidates]

        hybrid_results = self.optimizer.hybrid_search(
            query=query,
            documents=candidate_texts,
            top_k=top_k,
            bm25_weight=0.4,
            dense_weight=0.6,
        )

        final_docs = []
        for idx, score in hybrid_results:
            doc = candidates[idx]
            doc.metadata["hybrid_score"] = score
            final_docs.append(doc)

        return final_docs