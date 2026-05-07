# src/core/retriever.py

"""
Backward compatibility wrapper.

Yeni kullanım:
    from src.infrastructure.retrieval_service import RetrievalService

Eski kullanım:
    from src.core.retriever import SRSRetriever
"""

from src.infrastructure.retrieval_service import RetrievalService


class SRSRetriever(RetrievalService):
    pass
