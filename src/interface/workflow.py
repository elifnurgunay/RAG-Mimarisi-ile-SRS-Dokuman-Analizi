import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.retriever import SRSRetriever
from src.core.analyzer import SRSAnalyzer, calculate_score
from src.core.conflict_detector import ConflictDetector
from src.core.report_builder import ReportBuilder
from src.schemas.report import AnalysisReport
from src.core.deterministic_quality_rules import detect_deterministic_quality_issues
from src.utils.text_utils import clean_noise, split_into_batches
from src.utils.requirement_extractor import extract_requirements_from_chunks
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


class SRSWorkflow:
    def __init__(self):
        self.retriever = SRSRetriever(collection_name="elif_logic_collection")
        self.analyzer = None
        self.detector = ConflictDetector()  # varsayılan modelle başlat, run_conflict sırasında güncellenir

    def run_full_analysis(
        self,
        pdf_path: str,
        model_name: str = "llama-3.1-8b-instant",
        run_conflict: bool = False,
        top_k: int = 1,
    ):
        logger.info(
            "Workflow ayarları | model=%s | conflict=%s | top_k=%s",
            model_name,
            run_conflict,
            top_k,
        )

        self.analyzer = SRSAnalyzer(model_name=model_name)
        if run_conflict:
            self.detector = ConflictDetector(model_name=model_name)

        logger.info("İş akışı başladı | pdf=%s", pdf_path)

        if not self.retriever.load_and_index_pdf(pdf_path):
            logger.error("PDF okunamadı | pdf=%s", pdf_path)
            return None

        all_chunks = self.retriever.get_all_documents()

        if not all_chunks:
            logger.error("Veritabanından veri çekilemedi.")
            return None

        try:
            all_chunks.sort(key=lambda x: x.metadata.get("chunk_index", 0))
        except Exception as exc:
            logger.warning("Chunk sıralama başarısız | hata=%s", exc)

        chunk_texts = [
            clean_noise(doc.page_content)
            for doc in all_chunks
            if doc.page_content and doc.page_content.strip()
        ]

        batches = split_into_batches(chunk_texts, max_chars=5000)

        batch_reports = []
        for index, batch_text in enumerate(batches, start=1):
            logger.info("LLM analiz batch çalışıyor | batch=%d/%d", index, len(batches))
            partial_report = self.analyzer.analyze_text(
                batch_text,
                doc_name=f"{os.path.basename(pdf_path)}::batch-{index}",
            )
            if partial_report:
                batch_reports.append(partial_report)

        if not batch_reports:
            logger.error("Hiçbir batch raporu oluşturulamadı.")
            return None

        llm_issues = []
        for partial in batch_reports:
            llm_issues.extend(partial.issues)

        full_text = "\n".join(chunk_texts)

        deterministic_issues = detect_deterministic_quality_issues(full_text)
        
        merged_issues = self.analyzer.engine.merge_issues(
            llm_issues=llm_issues, 
            deterministic_issues=deterministic_issues, 
            document_text=full_text
        )

        report = AnalysisReport(
            document_name=os.path.basename(pdf_path),
            overall_quality_score=calculate_score(merged_issues),
            issues=merged_issues,
        )

        conflict_objects = []

        if run_conflict:
            logger.info("Çelişki analizi yapılıyor | mode=global_batch")

            req_texts, req_ids = extract_requirements_from_chunks(all_chunks)
            logger.info("Requirement extraction tamamlandı | requirement_sayısı=%d", len(req_texts))

            if not req_texts:
                logger.warning("REQ/FR/NFR/IR/DR/SR formatında requirement bulunamadı; çelişki analizi atlandı.")
            else:
                conflict_objects = self.detector.analyze_global_conflicts(
                    requirements=req_texts,
                    source_req_ids=req_ids,
                    top_k_candidates=top_k,
                )
        else:
            logger.info("Çelişki analizi kullanıcı seçimi nedeniyle atlandı.")

        final_report = ReportBuilder().build(
            analysis_report=report,
            conflicts=conflict_objects,
            source_text=full_text,
            output_language="auto",
        )
        return final_report