"""
src/core/report_builder.py

Kalite hataları + çelişkiler + skor + özeti birleştirerek
FinalSRSReport üretmekten sorumlu modül.

SRSAnalyzer      -> AnalysisReport (kalite hataları)
ConflictDetector -> List[ConflictIssue] (çelişkiler)
ReportBuilder    -> FinalSRSReport (nihai birleşik rapor)

Dil kuralı:
- SRS İngilizce ise final rapor İngilizce üretilir.
- SRS Türkçe ise final rapor Türkçe üretilir.
- JSON keyleri ve schema enum değerleri değiştirilmez.
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


# ---------------------------------------------------------------------------
# Dil algılama
# ---------------------------------------------------------------------------
_TURKISH_CHARS = set("çğıöşüÇĞİÖŞÜ")

_TURKISH_HINTS = [
    " gereksinim ",
    " sistem ",
    " kullanıcı ",
    " olmalıdır ",
    " olmamalıdır ",
    " içinde ",
    " için ",
    " veya ",
    " veri ",
    " güvenlik ",
    " çelişki ",
    " hata ",
    " öneri ",
]

_ENGLISH_HINTS = [
    " requirement ",
    " system ",
    " user ",
    " shall ",
    " should ",
    " must ",
    " must not ",
    " within ",
    " data ",
    " security ",
    " conflict ",
    " issue ",
    " recommendation ",
]


def _normalize_lang_code(language: Optional[str]) -> Optional[str]:
    if not language:
        return None

    value = language.strip().lower()

    if value in {"tr", "turkish", "türkçe", "turkce"}:
        return "tr"

    if value in {"en", "english", "ingilizce"}:
        return "en"

    if value == "auto":
        return None

    return None


def _detect_output_language(text: str) -> str:
    """
    Basit ve deterministik dil algılama.

    Öncelik:
    - İngilizce SRS içindeki 'shall', 'requirement', 'system', 'user' gibi ifadeler
    - Türkçe SRS içindeki 'gereksinim', 'olmalıdır', 'kullanıcı' gibi ifadeler

    Not:
    Tek bir Türkçe karakter gördüğü anda TR seçmez.
    Çünkü analyzer daha önce Türkçe issue üretmiş olabilir.
    """
    if not text or not text.strip():
        return "tr"

    sample = f" {text.lower()} "

    tr_score = 0
    en_score = 0

    tr_score += sum(2 for hint in _TURKISH_HINTS if hint in sample)
    en_score += sum(2 for hint in _ENGLISH_HINTS if hint in sample)

    # Türkçe karakter sinyali güçlüdür ama tek başına mutlak karar değildir.
    tr_score += sum(1 for ch in text if ch in _TURKISH_CHARS)

    # SRS İngilizcesinde çok sık görülen kalıplar.
    english_requirement_patterns = [
        " req-",
        " the system shall ",
        " system shall ",
        " shall ",
        " software requirements specification",
        " requirement ",
        " requirements ",
        " user ",
        " users ",
        " data ",
        " security ",
    ]

    en_score += sum(3 for pattern in english_requirement_patterns if pattern in sample)

    # Türkçe SRS kalıpları.
    turkish_requirement_patterns = [
        " gereksinim ",
        " sistem ",
        " kullanıcı ",
        " kullanıcılar ",
        " olmalıdır ",
        " olmamalıdır ",
        " veri ",
        " güvenlik ",
    ]

    tr_score += sum(3 for pattern in turkish_requirement_patterns if pattern in sample)

    if en_score > tr_score:
        return "en"

    return "tr"


def _collect_language_sample(
    analysis_report: AnalysisReport,
    conflicts: List[ConflictIssue],
    source_text: Optional[str],
) -> str:
    """
    Dil algılama için örnek metin toplar.

    Öncelik:
    1. Orijinal SRS metni
    2. Analyzer tarafından üretilen issue açıklamaları
    3. Conflict reason alanları
    4. Doküman adı
    """
    parts: List[str] = []

    if source_text:
        parts.append(source_text[:8000])

    for issue in analysis_report.issues:
        parts.append(getattr(issue, "problem", "") or "")
        parts.append(getattr(issue, "suggestion", "") or "")
        parts.append(getattr(issue, "req_id", "") or "")

    for conflict in conflicts:
        parts.append(getattr(conflict, "reason", "") or "")
        parts.append(getattr(conflict, "conflict_with_text", "") or "")

    parts.append(analysis_report.document_name or "")

    return "\n".join(part for part in parts if part)


# ---------------------------------------------------------------------------
# Skor hesaplama
# ---------------------------------------------------------------------------
def _calculate_quality_score(
    issues: List[RequirementIssue],
    conflicts: List[ConflictIssue],
) -> int:
    """
    Kalite puanını hesaplar.

    Başlangıç: 100
    Her kalite hatası -> ağırlığı kadar eksilir.
    Her çelişki bulgusu -> ağırlığı kadar eksilir.
    Minimum: 0
    """
    score = 100

    for issue in issues:
        score -= _ISSUE_WEIGHTS.get(issue.severity, 0)

    for conflict in conflicts:
        score -= _CONFLICT_WEIGHTS.get(conflict.severity, 0)

    return max(0, score)


# ---------------------------------------------------------------------------
# Öneri üretimi
# ---------------------------------------------------------------------------
def _generate_recommendations_tr(
    issues: List[RequirementIssue],
    conflicts: List[ConflictIssue],
) -> List[str]:
    recs: List[str] = []

    critical_issues = [i for i in issues if i.severity == "Critical"]
    if critical_issues:
        recs.append(
            f"{len(critical_issues)} adet kritik hata tespit edildi. "
            "Bu maddeler öncelikli olarak düzeltilmelidir."
        )

    high_conflicts = [c for c in conflicts if c.severity == "High"]
    if high_conflicts:
        recs.append(
            f"{len(high_conflicts)} adet yüksek ciddiyetli çelişki bulundu. "
            "İlgili gereksinim çiftleri ekip tarafından gözden geçirilmelidir."
        )

    ambiguity_count = sum(1 for i in issues if i.type == "Ambiguity")
    if ambiguity_count > 0:
        recs.append(
            f"{ambiguity_count} gereksinim belirsiz ifade içeriyor. "
            "Bu gereksinimlere ölçülebilir ve doğrulanabilir kriterler eklenmelidir."
        )

    incompleteness_count = sum(1 for i in issues if i.type == "Incompleteness")
    if incompleteness_count > 0:
        recs.append(
            f"{incompleteness_count} gereksinim eksik bilgi içeriyor. "
            "Eksik aktör, koşul, veri veya kabul kriterleri tamamlanmalıdır."
        )

    inconsistency_count = sum(1 for i in issues if i.type == "Inconsistency")
    if inconsistency_count > 0:
        recs.append(
            f"{inconsistency_count} tutarsızlık veya tekrar problemi tespit edildi. "
            "Tekrarlanan veya farklı bölümlerde çakışan gereksinimler sadeleştirilmelidir."
        )

    testability_count = sum(1 for i in issues if i.type == "Testability")
    if testability_count > 0:
        recs.append(
            f"{testability_count} gereksinim test edilebilir değil. "
            "Bu maddeler için net kabul kriterleri ve test koşulları tanımlanmalıdır."
        )

    if not recs:
        recs.append(
            "Doküman genel olarak iyi kalitede görünüyor. "
            "Küçük ifade netleştirmeleri dışında kritik bir iyileştirme gerekmiyor."
        )

    return recs


def _generate_recommendations_en(
    issues: List[RequirementIssue],
    conflicts: List[ConflictIssue],
) -> List[str]:
    recs: List[str] = []

    critical_issues = [i for i in issues if i.severity == "Critical"]
    if critical_issues:
        recs.append(
            f"{len(critical_issues)} critical issue(s) were detected. "
            "These requirements should be corrected with highest priority."
        )

    high_conflicts = [c for c in conflicts if c.severity == "High"]
    if high_conflicts:
        recs.append(
            f"{len(high_conflicts)} high-severity conflict(s) were found. "
            "The related requirement pairs should be reviewed by the project team."
        )

    ambiguity_count = sum(1 for i in issues if i.type == "Ambiguity")
    if ambiguity_count > 0:
        recs.append(
            f"{ambiguity_count} requirement(s) contain ambiguous wording. "
            "Measurable and verifiable criteria should be added."
        )

    incompleteness_count = sum(1 for i in issues if i.type == "Incompleteness")
    if incompleteness_count > 0:
        recs.append(
            f"{incompleteness_count} requirement(s) contain incomplete information. "
            "Missing actors, conditions, data, or acceptance criteria should be completed."
        )

    inconsistency_count = sum(1 for i in issues if i.type == "Inconsistency")
    if inconsistency_count > 0:
        recs.append(
            f"{inconsistency_count} inconsistency or duplication issue(s) were detected. "
            "Repeated or conflicting requirements across sections should be consolidated."
        )

    testability_count = sum(1 for i in issues if i.type == "Testability")
    if testability_count > 0:
        recs.append(
            f"{testability_count} requirement(s) are not testable. "
            "Clear acceptance criteria and test conditions should be defined."
        )

    if not recs:
        recs.append(
            "The document appears to be generally well structured. "
            "Only minor wording improvements are recommended."
        )

    return recs


def _generate_recommendations(
    issues: List[RequirementIssue],
    conflicts: List[ConflictIssue],
    language: str,
) -> List[str]:
    if language == "en":
        return _generate_recommendations_en(issues, conflicts)

    return _generate_recommendations_tr(issues, conflicts)


# ---------------------------------------------------------------------------
# ReportBuilder
# ---------------------------------------------------------------------------
class ReportBuilder:
    """
    Ham analiz çıktılarını birleştirip FinalSRSReport üretir.

    Kullanım:
        builder = ReportBuilder()
        final = builder.build(analysis_report, conflict_issues)

    Daha doğru dil algılama için:
        final = builder.build(
            analysis_report,
            conflict_issues,
            source_text=document_text,
        )
    """

    def build(
        self,
        analysis_report: AnalysisReport,
        conflicts: Optional[List[ConflictIssue]] = None,
        executive_summary: Optional[str] = None,
        output_language: Optional[str] = "auto",
        source_text: Optional[str] = None,
    ) -> FinalSRSReport:
        conflicts = conflicts or []
        raw_issues = analysis_report.issues

        unique_issues = {}
        for issue in raw_issues:
            req_id = getattr(issue, "req_id", "")
            itype = getattr(issue, "type", "")
            problem = getattr(issue, "problem", "")
            key = f"{req_id}::{itype}::{problem}"
            if key not in unique_issues:
                unique_issues[key] = issue

        deduped_issues = list(unique_issues.values())

        severity_map = {"High": 0, "Medium": 1, "Low": 2}
        deduped_issues.sort(key=lambda x: severity_map.get(getattr(x, "severity", "Low"), 3))

        MAX_TOTAL_QUALITY_ISSUES = 20
        capped_issues = deduped_issues[:MAX_TOTAL_QUALITY_ISSUES]

        normalized_language = _normalize_lang_code(output_language)

        if normalized_language is None:
            if source_text and source_text.strip():
                normalized_language = _detect_output_language(source_text)
            else:
                language_sample = _collect_language_sample(
                    analysis_report=analysis_report,
                    conflicts=conflicts,
                    source_text=None,
                )
                normalized_language = _detect_output_language(language_sample)

        score = _calculate_quality_score(capped_issues, conflicts)
        recommendations = _generate_recommendations(
            issues=capped_issues,
            conflicts=conflicts,
            language=normalized_language,
        )

        if not executive_summary:
            executive_summary = self._auto_summary(
                doc_name=analysis_report.document_name,
                score=score,
                issue_count=len(capped_issues),
                conflict_count=len(conflicts),
                language=normalized_language,
            )

        final = FinalSRSReport(
            document_name=analysis_report.document_name,
            overall_quality_score=score,
            total_issues=len(capped_issues),
            total_conflicts=len(conflicts),
            quality_issues=capped_issues,
            conflicts=conflicts,
            language=normalized_language,
            executive_summary=executive_summary,
            recommendations=recommendations,
        )

        logger.info(
            "Final rapor oluşturuldu | belge=%s | skor=%d | hata=%d | çelişki=%d | dil=%s",
            final.document_name,
            final.overall_quality_score,
            final.total_issues,
            final.total_conflicts,
            normalized_language,
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
        language: str,
    ) -> str:
        if language == "en":
            return ReportBuilder._auto_summary_en(
                doc_name=doc_name,
                score=score,
                issue_count=issue_count,
                conflict_count=conflict_count,
            )

        return ReportBuilder._auto_summary_tr(
            doc_name=doc_name,
            score=score,
            issue_count=issue_count,
            conflict_count=conflict_count,
        )

    @staticmethod
    def _auto_summary_tr(
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

    @staticmethod
    def _auto_summary_en(
        doc_name: str,
        score: int,
        issue_count: int,
        conflict_count: int,
    ) -> str:
        if score >= 80:
            quality_label = "Good"
        elif score >= 60:
            quality_label = "Moderate"
        else:
            quality_label = "Poor"

        return (
            f"'{doc_name}' was analyzed. "
            f"Overall quality level: **{quality_label}** (Score: {score}/100). "
            f"A total of {issue_count} quality issue(s) and {conflict_count} conflict(s) were detected."
        )