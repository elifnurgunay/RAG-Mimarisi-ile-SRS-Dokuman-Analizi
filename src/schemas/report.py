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
    Raw quality report returned from LLM in a single analysis round.
    Produced by SRSAnalyzer.
    """

    document_name: str = Field(..., description="Name of the analyzed SRS document.")
    overall_quality_score: int = Field(
        ..., ge=0, le=100, description="Overall quality score between 0 and 100."
    )
    issues: List[RequirementIssue] = Field(
        default_factory=list, description="List of detected requirement quality issues."
    )


class FinalSRSReport(BaseModel):
    """
    Final combined SRS analysis report created by ReportBuilder.
    Includes quality issues, conflicts, scores, and summary.
    """

    document_name: str = Field(..., description="Name of the analyzed SRS document.")
    analysis_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Analizin yapıldığı zaman damgası (ISO 8601)",
    )

    # --- Kalite Metrikleri ---
    overall_quality_score: int = Field(
        ..., ge=0, le=100, description="Overall quality score between 0 and 100."
    )
    total_issues: int = Field(default=0, description="Total number of detected quality issues.")
    total_conflicts: int = Field(
        default=0, description="Total number of detected conflicts."
    )

    # --- Detaylar ---
    quality_issues: List[RequirementIssue] = Field(
        default_factory=list, description="List of detected requirement quality issues."
    )
    conflicts: List[ConflictIssue] = Field(
        default_factory=list, description="List of detected requirement conflicts."
    )

    # --- Özet ---
    language: str = Field("en", description="Detected language of the document (tr or en)")
    executive_summary: Optional[str] = Field(
        default=None,
        description="Executive summary of the final report. Write this field in the same language as the input SRS text.",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Prioritized improvement recommendations. Write these items in the same language as the input SRS text.",
    )
