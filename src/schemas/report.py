"""
src/schemas/report.py

Analiz ve final rapor modellerini barındırır.
AnalysisReport  → LLM kalite analizi çıktısı
FinalSRSReport  → Kalite + çelişki + skor + özeti birleştiren nihai rapor
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from .issue import RequirementIssue, ConflictIssue


class AnalysisReport(BaseModel):
    """
    Tek bir analiz turunda LLM'den dönen ham kalite raporu.
    SRSAnalyzer tarafından üretilir.
    """

    document_name: str = Field(..., description="Analiz edilen dokümanın adı")
    overall_quality_score: int = Field(
        ..., ge=0, le=100, description="0–100 arası kalite skoru"
    )
    issues: List[RequirementIssue] = Field(
        default_factory=list, description="Tespit edilen tüm kalite hataları"
    )


class FinalSRSReport(BaseModel):
    """
    ReportBuilder tarafından oluşturulan nihai, birleşik SRS analiz raporu.
    Kalite hataları + çelişkiler + skor + özet içerir.
    """

    document_name: str = Field(..., description="Analiz edilen dokümanın adı")
    analysis_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Analizin yapıldığı zaman damgası (ISO 8601)",
    )

    # --- Kalite Metrikleri ---
    overall_quality_score: int = Field(
        ..., ge=0, le=100, description="Kalite puanı (100 = mükemmel)"
    )
    total_issues: int = Field(default=0, description="Toplam tespit edilen hata sayısı")
    total_conflicts: int = Field(
        default=0, description="Toplam tespit edilen çelişki sayısı"
    )

    # --- Detaylar ---
    quality_issues: List[RequirementIssue] = Field(
        default_factory=list, description="Kalite hataları listesi"
    )
    conflicts: List[ConflictIssue] = Field(
        default_factory=list, description="Çelişki bulguları listesi"
    )

    # --- Özet ---
    executive_summary: Optional[str] = Field(
        default=None,
        description="Yönetici için kısa doküman özeti",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Öncelikli iyileştirme önerileri listesi",
    )
