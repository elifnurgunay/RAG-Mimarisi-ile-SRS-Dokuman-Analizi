# src/infrastructure/retrieval_service.py

import os

from langchain_core.documents import Document

from src.config import QDRANT_COLLECTION_NAME, REQUIREMENT_ID_PATTERN
from src.infrastructure.hybrid_qdrant_store import HybridQdrantStore
from src.infrastructure.pdf_loader import PDFLoaderService
from src.parsing.chunking_strategy import ReqChunkingStrategy
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


class RetrievalService:
    def __init__(self, collection_name: str = QDRANT_COLLECTION_NAME):
        self.collection_name = collection_name

        self.pdf_loader = PDFLoaderService()
        self.hybrid_store = HybridQdrantStore(collection_name=self.collection_name)

        self.chunk_strategy = ReqChunkingStrategy(
            req_pattern=REQUIREMENT_ID_PATTERN,
            fallback_chunk_size=500,
            fallback_overlap=50,
        )

    def load_and_index_pdf(self, pdf_path: str) -> bool:
        if not os.path.exists(pdf_path):
            logger.error("Dosya bulunamadı | path=%s", pdf_path)
            return False

        documents = self.pdf_loader.load(pdf_path)
        chunks = self.chunk_strategy.chunk_documents(documents)

        chunks = [
            doc
            for doc in chunks
            if doc.page_content and doc.page_content.strip()
        ]

        if not chunks:
            logger.warning("Indexlenecek geçerli metin bulunamadı.")
            return False

        self.hybrid_store.add_documents(
            chunks,
            force_recreate=True,
        )

        logger.info("Indexleme tamamlandı | chunk_sayısı=%d", len(chunks))
        return True

    def add_structured_data(self, requirements_json: list) -> bool:
        docs = [
            Document(
                page_content=req["text"],
                metadata={"req_id": req["id"]},
            )
            for req in requirements_json
            if req.get("text")
        ]

        if not docs:
            return False

        self.hybrid_store.add_documents(
            docs,
            force_recreate=False,
        )

        return True

    def get_all_documents(self, k: int = 100):
        return self.hybrid_store.scroll_all_documents(limit=k)

    def get_similar_requirements(self, query: str, top_k: int = 3):
        return self.hybrid_store.hybrid_search(
            query=query,
            top_k=top_k,
        )