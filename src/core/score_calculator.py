# src/core/score_calculator.py

from typing import List
from src.schemas.issue import RequirementIssue


def calculate_score(issues: List[RequirementIssue]) -> int:
    """Hataların ciddiyetine göre 100 üzerinden kalite puanı hesaplar."""
    score = 100
    weights = {
        "Critical": 20,
        "High": 10,
        "Medium": 5,
        "Low": 2,
    }

    for issue in issues:
        score -= weights.get(issue.severity, 0)

    return max(0, score)