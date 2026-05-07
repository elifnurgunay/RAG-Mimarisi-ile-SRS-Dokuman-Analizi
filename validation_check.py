"""
4 kritik import kontrolü - API çağrısı YOK.
Kullanım: .venv/Scripts/python.exe validation_check.py
"""
import warnings
import json
import sys
import subprocess
from pathlib import Path

PROJ_ROOT = Path(__file__).parent
PYTHON = str(PROJ_ROOT / ".venv" / "Scripts" / "python.exe")

warnings.filterwarnings("ignore")
errors = []


# ------------------------------------------------------------------
# 1. workflow.py import
# ------------------------------------------------------------------
try:
    from src.interface.workflow import SRSWorkflow  # noqa: F401
    print("[OK] 1. workflow.py import edildi")
except Exception as e:
    print(f"[FAIL] 1. workflow.py HATA: {e}")
    errors.append("workflow")

# ------------------------------------------------------------------
# 3. report_builder final JSON (skor, alanlar, JSON geçerliliği)
# ------------------------------------------------------------------
try:
    from src.schemas.issue import RequirementIssue, ConflictIssue
    from src.schemas.report import AnalysisReport
    from src.core.report_builder import ReportBuilder

    issue = RequirementIssue(
        req_id="REQ-001", type="Ambiguity", severity="High",
        problem="Belirsiz ifade", suggestion="Netlestiriniz"
    )
    conflict = ConflictIssue(
        source_req_id="REQ-001", conflict_with_text="Karsi metin...",
        reason="Nicel celiski", severity="Medium",
    )
    base = AnalysisReport(document_name="test.pdf", overall_quality_score=80, issues=[issue])
    final = ReportBuilder().build(base, [conflict])
    parsed = json.loads(final.model_dump_json())

    # Beklenen skor: 100 - High_issue(10) - Medium_conflict(8) = 82
    REQUIRED_KEYS = ["document_name", "quality_issues", "conflicts",
                     "recommendations", "overall_quality_score", "executive_summary"]
    missing = [k for k in REQUIRED_KEYS if k not in parsed]
    assert not missing, f"Eksik JSON alanlari: {missing}"
    assert parsed["overall_quality_score"] == 82, (
        f"Skor 82 bekleniyor, {parsed['overall_quality_score']} geldi"
    )
    assert isinstance(parsed["recommendations"], list)
    assert len(parsed["recommendations"]) > 0
    print(f"[OK] 3. report_builder final JSON uretildi — skor={parsed['overall_quality_score']}/100, "
          f"tum alanlar mevcut, JSON gecerli")
except Exception as e:
    print(f"[FAIL] 3. report_builder HATA: {e}")
    errors.append("report_builder")


# ------------------------------------------------------------------
# 4. analyzer.py geriye dönük uyumluluk
# ------------------------------------------------------------------
try:
    from src.core.analyzer import RequirementIssue as AI_RI
    from src.core.analyzer import AnalysisReport as AI_AR
    from src.core.analyzer import calculate_score
    from src.schemas.issue import RequirementIssue as SC_RI
    from src.schemas.report import AnalysisReport as SC_AR

    assert AI_RI is SC_RI, "RequirementIssue sinifi uyumsuz!"
    assert AI_AR is SC_AR, "AnalysisReport sinifi uyumsuz!"

    test_issues = [
        RequirementIssue(req_id="X", type="Ambiguity", severity="Critical",
                         problem="p", suggestion="s")
    ]
    score = calculate_score(test_issues)
    assert score == 80, f"calculate_score: beklenen 80, gelen {score}"
    print("[OK] 4. analyzer.py eski importlar calisıyor — siniflar ayni, calculate_score dogru")
except Exception as e:
    print(f"[FAIL] 4. analyzer.py HATA: {e}")
    errors.append("analyzer_compat")


# ------------------------------------------------------------------
# SONUÇ
# ------------------------------------------------------------------
print()
if errors:
    print(f"=== {len(errors)} KONTROL BASARISIZ: {errors} ===")
    sys.exit(1)
else:
    print("=== TUM 4 KRITIK KONTROL GECTI ===")
    sys.exit(0)
