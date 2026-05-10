"""
main.py — Terminal giriş noktası

Kullanım:
    python main.py data/SRSDocument.pdf
    python main.py data/SRSDocument.pdf --output rapor.json

Pipeline:
    1. PDF → Qdrant index (SRSRetriever)
    2. Metin kalite analizi (SRSAnalyzer)
    3. Çelişki tespiti (ConflictDetector)
    4. Nihai rapor üretimi (ReportBuilder)
    5. JSON çıktısı
"""
import sys
import os
import argparse
import json
import time
from src.utils.text_utils import clean_noise, split_into_batches
from src.utils.requirement_extractor import extract_requirements_from_chunks
from src.schemas.report import AnalysisReport
from src.core.analyzer import calculate_score
# Proje kökünü Python path'ine ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import validate as validate_config
from src.utils.logging_utils import get_logger

logger = get_logger("main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="srs-analyzer",
        description="RAG tabanlı SRS Doküman Analiz Motoru",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Örnekler:\n"
            "  python main.py data/SRSDocument.pdf\n"
            "  python main.py data/SRSDocument.pdf --output cikti/rapor.json\n"
            "  python main.py data/SRSDocument.pdf --top-k 5 --no-conflict\n"
        ),
    )
    parser.add_argument(
        "pdf_path",
        metavar="PDF_DOSYASI",
        help="Analiz edilecek SRS PDF dosyasının yolu",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="DOSYA",
        default=None,
        help="Raporu kaydedeceğiniz JSON dosya yolu (varsayılan: stdout)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Çelişki tespitinde her gereksinim için kullanılacak aday sayısı (varsayılan: 3)",
    )
    parser.add_argument(
        "--no-conflict",
        action="store_true",
        help="Çelişki analiz adımını atla (daha hızlı çalışır)",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Qdrant koleksiyon adı (varsayılan: config.py'den alınır)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Kullanılacak Groq model adı (ör: llama-3.1-8b-instant)",
    )
    return parser.parse_args()


def run_pipeline(args: argparse.Namespace) -> dict:
    """Tam analiz pipeline'ını çalıştırır ve sonuç dict'i döndürür."""

    # Geç import (config doğrulandıktan sonra)
    from src.core.retriever import SRSRetriever
    from src.core.analyzer import SRSAnalyzer
    from src.core.conflict_detector import ConflictDetector
    from src.core.report_builder import ReportBuilder
    from src.schemas.issue import ConflictIssue

    pdf_path = args.pdf_path
    if not os.path.exists(pdf_path):
        logger.error("Dosya bulunamadı: %s", pdf_path)
        sys.exit(1)

    start_time = time.time()
    logger.info("=" * 60)
    logger.info("SRS Analiz Motoru başlatıldı")
    logger.info("Dosya : %s", pdf_path)
    logger.info("=" * 60)

    # 1. PDF → Qdrant index
    logger.info("[1/4] PDF indexleniyor...")
    collection = args.collection  # None ise retriever kendi varsayılanını kullanır
    retriever = SRSRetriever(collection_name=collection) if collection else SRSRetriever()
    if not retriever.load_and_index_pdf(pdf_path):
        logger.error("PDF okunamadı / indexlenemedi.")
        sys.exit(1)

    # 2. Tüm dokümanı çek ve kalite analizi yap
    logger.info("[2/4] Doküman metni çekiliyor...")
    all_chunks = retriever.get_all_documents()
    if not all_chunks:
        logger.error("Veritabanından veri çekilemedi.")
        sys.exit(1)

    chunk_texts = [
        clean_noise(doc.page_content)
        for doc in all_chunks
        if doc.page_content and doc.page_content.strip()
    ]

    batches = split_into_batches(chunk_texts, max_chars=5000)

    logger.info("[3/4] LLM kalite analizi çalışıyor | batch=%d", len(batches))

    analyzer = SRSAnalyzer(model_name=args.model)
    batch_reports = []

    for index, batch_text in enumerate(batches, start=1):
        logger.info("LLM analiz batch çalışıyor: %d/%d", index, len(batches))

        partial_report = analyzer.analyze_text(
            batch_text,
            doc_name=f"{os.path.basename(pdf_path)}::batch-{index}",
        )

        if partial_report:
            batch_reports.append(partial_report)

    if not batch_reports:
        logger.error("Hiçbir batch raporu oluşturulamadı; conflict analizi çalıştırılmayacak.")
        sys.exit(1)

    merged_issues = []
    for partial in batch_reports:
        merged_issues.extend(partial.issues)

    analysis_report = AnalysisReport(
        document_name=os.path.basename(pdf_path),
        overall_quality_score=calculate_score(merged_issues),
        issues=merged_issues,
    )
    # 3. Çelişki tespiti (opsiyonel)
    conflict_issues: list[ConflictIssue] = []

    if not args.no_conflict:
        logger.info("[4/4] Çelişki analizi çalışıyor (top_k=%d)...", args.top_k)

        req_texts, req_ids = extract_requirements_from_chunks(all_chunks)
        logger.info("Requirement extraction tamamlandı | requirement_sayısı=%d", len(req_texts))

        if not req_texts:
            logger.warning("REQ/FR/NFR/IR/DR/SR formatında requirement bulunamadı; çelişki analizi atlandı.")
        else:
            detector = ConflictDetector(model_name=args.model)
            conflict_issues = detector.analyze_global_conflicts(
                requirements=req_texts,
                source_req_ids=req_ids,
                top_k_candidates=args.top_k,
            )
    else:
        logger.info("[4/4] Çelişki analizi atlandı (--no-conflict).")

    # 4. Final raporu oluştur
    builder = ReportBuilder()
    final_report = builder.build(
        analysis_report,
        conflict_issues,
        source_text="\n".join(chunk_texts),
        output_language="auto",
    )
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("Analiz tamamlandı | Süre: %.1f sn | Skor: %d/100",
                elapsed, final_report.overall_quality_score)
    logger.info("Kalite hatası: %d | Çelişki: %d",
                final_report.total_issues, final_report.total_conflicts)
    logger.info("=" * 60)

    return json.loads(final_report.model_dump_json(indent=2))


def main() -> None:
    args = parse_args()

    # Konfigürasyonu doğrula
    try:
        validate_config()
    except ValueError as exc:
        print(f"[HATA] {exc}", file=sys.stderr)
        sys.exit(1)

    result = run_pipeline(args)

    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        logger.info("Rapor kaydedildi: %s", args.output)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
