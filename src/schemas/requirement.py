"""
src/schemas/requirement.py

Tekil bir gereksinim maddesini temsil eden Pydantic modeli.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class Requirement(BaseModel):
    """SRS dokümanındaki tek bir gereksinim maddesini temsil eder."""

    model_config = ConfigDict(populate_by_name=True)

    req_id: str = Field(..., description="Gereksinimin benzersiz ID'si (ör. REQ-001)")
    text: str = Field(..., description="Gereksinimin tam metni")
    section: Optional[str] = Field(
        default=None, description="Gereksinimin ait olduğu bölüm başlığı"
    )
    source_page: Optional[int] = Field(
        default=None, description="PDF'deki kaynak sayfa numarası"
    )
