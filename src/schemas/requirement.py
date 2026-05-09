"""
src/schemas/requirement.py

Tekil bir gereksinim maddesini temsil eden Pydantic modeli.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class Requirement(BaseModel):
    """Represents a single requirement item in the SRS document."""

    model_config = ConfigDict(populate_by_name=True)

    req_id: str = Field(..., description="Unique requirement ID, such as REQ-001.")
    text: str = Field(..., description="Full requirement text.")
    section: Optional[str] = Field(
        default=None, description="Section title where the requirement appears."
    )
    source_page: Optional[int] = Field(
        default=None, description="Source page number in the PDF."
    )
