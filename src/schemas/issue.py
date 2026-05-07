"""
src/schemas/issue.py

Kalite hatalarını ve çelişki bulgularını temsil eden Pydantic modelleri.
Daha önce analyzer.py içinde tanımlıydı; buraya taşındı.
"""
from pydantic import BaseModel, Field
from typing import Literal, Optional


class RequirementIssue(BaseModel):
    """
    Tek bir gereksinim maddesinde tespit edilen kalite hatasını temsil eder.
    LLM çıktısını doğrudan parse etmek için kullanılır.
    """

    req_id: str = Field(..., description="Analiz edilen gereksinimin ID'si")
    type: Literal["Ambiguity", "Inconsistency", "Incompleteness", "Testability"] = Field(
        ..., description="Hata tipi (ISO/IEC/IEEE 29148)"
    )
    severity: Literal["Critical", "High", "Medium", "Low"] = Field(
        ..., description="Ciddiyet seviyesi"
    )
    problem: str = Field(..., description="Tespit edilen sorunun teknik açıklaması")
    suggestion: str = Field(..., description="Düzeltme önerisi")


class ConflictIssue(BaseModel):
    """
    İki gereksinim maddesi arasında tespit edilen çelişkiyi temsil eder.
    ConflictDetector tarafından üretilir.
    """

    source_req_id: str = Field(..., description="Çelişkiyi tetikleyen kaynak gereksinim ID'si")
    conflict_with_text: str = Field(
        ..., description="Çelişen karşı metnin ilk ~80 karakteri"
    )
    reason: str = Field(..., description="Çelişkinin açıklaması")
    severity: Literal["Low", "Medium", "High"] = Field(
        ..., description="Çelişki ciddiyeti"
    )
    conflict_type: Optional[str] = Field(
        default=None,
        description="Çelişki türü: Quantitative / Logical / Scope / Terminology",
    )
