"""
src/core/analyzer.py

LLM tabanlı SRS kalite analiz motoru.
Public facade olarak kalır; batching, prompt ve engine işleri ayrı modüllerdedir.
"""

from langchain_core.output_parsers import JsonOutputParser

from src.core.llm_client import get_llm
from src.core.batch_processor import BatchProcessor
from src.core.analysis_engine import AnalysisEngine
from src.core.score_calculator import calculate_score
from src.schemas.issue import RequirementIssue
from src.schemas.report import AnalysisReport

__all__ = ["RequirementIssue", "AnalysisReport", "calculate_score", "SRSAnalyzer"]


class SRSAnalyzer:
    def __init__(self):
        self.llm = get_llm()
        self.parser = JsonOutputParser(pydantic_object=AnalysisReport)
        self.batch_processor = BatchProcessor(max_chars=50000)
        self.engine = AnalysisEngine(llm=self.llm, parser=self.parser)

    def run_analysis(self, chunk_text: str, metadata: dict = None) -> AnalysisReport:
        """Tek bir chunk için analiz çalıştırır."""
        return self.analyze_text(chunk_text, doc_name="Chunk", metadata=metadata)

    def analyze_text(
        self,
        srs_text: str,
        doc_name: str = "Doküman",
        metadata: dict = None,
    ) -> AnalysisReport:
        """
        Gereksinimleri batch'lere bölerek LLM tabanlı kalite analizi yapar.
        """
        batches = self.batch_processor.create_batches(srs_text)

        issues = self.engine.analyze_batches(
            batches=batches,
            metadata=metadata,
        )

        return AnalysisReport(
            document_name=doc_name,
            overall_quality_score=calculate_score(issues),
            issues=issues,
        )