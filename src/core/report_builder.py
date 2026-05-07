"""
src/core/report_builder.py

Kalite hataları + çelişkiler + skor + özeti birleştirerek
FinalSRSReport üretmekten sorumlu modül.

SRSAnalyzer  → AnalysisReport (kalite hataları)
ConflictDetector → List[ConflictIssue] (çelişkiler)
ReportBuilder → FinalSRSReport (nihai birleşik rapor)
"""
from typing import List, Optional

from src.schemas.issue import RequirementIssue, ConflictIssue
from src.schemas.report import AnalysisReport, FinalSRSReport
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Ağırlıklar (skor hesaplama)
# ---------------------------------------------------------------------------
_ISSUE_WEIGHTS = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
_CONFLICT_WEIGHTS = {"High": 15, "Medium": 8, "Low": 3}


def _calculate_quality_score(
    issues: List[RequirementIssue],
    conflicts: List[ConflictIssue],
) -> int:
    """
    Kalite puanını hesaplar (0–100).

    Başlangıç: 100
    Her kalite hatası → ağırlığı kadar eksilir.
    Her çelişki bulgusu → ağırlığı kadar eksilir.
    Minimum: 0
    """
    score = 100

    for issue in issues:
        score -= _ISSUE_WEIGHTS.get(issue.severity, 0)

    for conflict in conflicts:
        score -= _CONFLICT_WEIGHTS.get(conflict.severity, 0)

    return max(0, score)


def _generate_recommendations(
    issues: List[RequirementIssue],
    conflicts: List[ConflictIssue],
) -> List[str]:
    """Bulgulara göre öncelikli iyileştirme önerileri üretir."""
    recs: List[str] = []

    critical_issues = [i for i in issues if i.severity == "Critical"]
    if critical_issues:
        recs.append(
            f"{len(critical_issues)} adet KRİTİK hata tespit edildi. "
            "Bu maddelerin ivedilikle düzeltilmesi gerekir."
        )

    high_conflicts = [c for c in conflicts if c.severity == "High"]
    if high_conflicts:
        recs.append(
            f"{len(high_conflicts)} adet YÜKSEK ciddiyetli çelişki bulundu. "
            "İlgili gereksinim çiftleri ekip toplantısında gözden geçirilmeli."
        )

    ambiguity_count = sum(1 for i in issues if i.type == "Ambiguity")
    if ambiguity_count > 0:
        recs.append(
            f"{ambiguity_count} gereksinim belirsiz ifade içeriyor. "
            "Ölçülebilir kriterler eklenmeli."
        )

    testability_count = sum(1 for i in issues if i.type == "Testability")
    if testability_count > 0:
        recs.append(
            f"{testability_count} gereksinim test edilemez durumda. "
            "Kabul kriterleri netleştirilmeli."
        )

    if not recs:
        recs.append("Doküman genel olarak iyi kalitede görünüyor. Küçük iyileştirmeler önerilir.")

    return recs


class ReportBuilder:
    """
    Ham analiz çıktılarını birleştirip FinalSRSReport üretir.

    Kullanım:
        builder = ReportBuilder()
        final = builder.build(analysis_report, conflict_issues)
    """

    def build(
        self,
        analysis_report: AnalysisReport,
        conflicts: Optional[List[ConflictIssue]] = None,
        executive_summary: Optional[str] = None,
    ) -> FinalSRSReport:
        """
        FinalSRSReport oluşturur.

        Args:
            analysis_report:   SRSAnalyzer'dan gelen kalite raporu.
            conflicts:         ConflictDetector'dan gelen çelişki listesi (None ise boş).
            executive_summary: Harici olarak sağlanan yönetici özeti (opsiyonel).

        Returns:
            Eksiksiz FinalSRSReport nesnesi.
        """
        conflicts = conflicts or []
        issues = analysis_report.issues

        score = _calculate_quality_score(issues, conflicts)
        recommendations = _generate_recommendations(issues, conflicts)

        # Otomatik özet üretimi (harici verilmemişse)
        if not executive_summary:
            executive_summary = self._auto_summary(
                doc_name=analysis_report.document_name,
                score=score,
                issue_count=len(issues),
                conflict_count=len(conflicts),
            )

        final = FinalSRSReport(
            document_name=analysis_report.document_name,
            overall_quality_score=score,
            total_issues=len(issues),
            total_conflicts=len(conflicts),
            quality_issues=issues,
            conflicts=conflicts,
            executive_summary=executive_summary,
            recommendations=recommendations,
        )

        logger.info(
            "Final rapor oluşturuldu | belge=%s | skor=%d | hata=%d | çelişki=%d",
            final.document_name,
            final.overall_quality_score,
            final.total_issues,
            final.total_conflicts,
        )
        return final

    # ------------------------------------------------------------------
    # Yardımcı: otomatik özet metni
    # ------------------------------------------------------------------
    @staticmethod
    def _auto_summary(
        doc_name: str,
        score: int,
        issue_count: int,
        conflict_count: int,
    ) -> str:
        if score >= 80:
            quality_label = "İyi"
        elif score >= 60:
            quality_label = "Orta"
        else:
            quality_label = "Zayıf"

        return (
            f"'{doc_name}' dokümanı analiz edildi. "
            f"Genel kalite seviyesi: **{quality_label}** (Skor: {score}/100). "
            f"Toplam {issue_count} kalite hatası ve {conflict_count} çelişki tespit edildi."
        )
