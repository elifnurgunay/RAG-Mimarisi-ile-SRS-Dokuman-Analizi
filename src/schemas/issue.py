"""
src/schemas/issue.py

Kalite hatalarını ve çelişki bulgularını temsil eden Pydantic modelleri.
Daha önce analyzer.py içinde tanımlıydı; buraya taşındı.
"""
from pydantic import BaseModel, Field
from typing import Literal, Optional


class RequirementIssue(BaseModel):
    """
    Represents a quality issue detected in a single requirement.
    Used for direct parsing of LLM output.
    """

    req_id: str = Field(..., description="ID of the analyzed requirement, such as REQ-001.")
    type: Literal["Ambiguity", "Inconsistency", "Incompleteness", "Testability"] = Field(
        ..., description="Issue category. Use one of: Ambiguity, Inconsistency, Incompleteness, Testability."
    )
    severity: Literal["Critical", "High", "Medium", "Low"] = Field(
        ..., description="Issue severity. Use one of: Low, Medium, High, Critical."
    )
    problem: str = Field(..., description="Technical explanation of the detected issue. Write this field in the same language as the input SRS text.")
    suggestion: str = Field(..., description="Concrete correction suggestion. Write this field in the same language as the input SRS text.")


class ConflictIssue(BaseModel):
    """
    Represents a conflict detected between two requirements.
    Produced by ConflictDetector.
    """

    source_req_id: str = Field(..., description="ID of the source requirement.")
    conflict_with_text: str = Field(
        ..., description="Short text excerpt of the conflicting requirement."
    )
    reason: str = Field(..., description="Technical explanation of why the requirements conflict. Write this field in the same language as the input SRS text.")
    severity: Literal["Low", "Medium", "High"] = Field(
        ..., description="Conflict severity. Use one of: Low, Medium, High."
    )
    conflict_type: Optional[str] = Field(
        default=None,
        description="Conflict type. Use one of: Quantitative, Logical, Scope, None.",
    )
