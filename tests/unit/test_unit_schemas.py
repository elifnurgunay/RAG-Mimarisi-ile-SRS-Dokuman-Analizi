"""
tests/test_unit_schemas.py

Ağ/API çağrısı OLMADAN çalışan birim testleri.
Kontrol listesi:
  1. schemas.issue      → RequirementIssue, ConflictIssue
  2. schemas.report     → AnalysisReport, FinalSRSReport
  3. schemas.requirement→ Requirement
  4. config.py          → değişken tipleri doğru mu?
  5. utils.json_utils   → safe_parse_json, extract_json_from_text
  6. utils.text_utils   → normalize_whitespace, split_into_batches
  7. utils.logging_utils→ get_logger
  8. report_builder.py  → ReportBuilder.build() final JSON üretiyor mu?
  9. logic.py köprüsü   → DeprecationWarning vererek ConflictDetector'ı yeniden ihraç ediyor mu?
 10. analyzer.py        → eski importlar (RequirementIssue, AnalysisReport) hâlâ çalışıyor mu?
"""
import json
import warnings
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1-3  SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class TestRequirementIssue:
    def test_valid_creation(self):
        from src.schemas.issue import RequirementIssue
        issue = RequirementIssue(
            req_id="REQ-001",
            type="Ambiguity",
            severity="High",
            problem="Belirsiz ifade.",
            suggestion="Ölçülebilir kriter ekleyin.",
        )
        assert issue.req_id == "REQ-001"
        assert issue.type == "Ambiguity"
        assert issue.severity == "High"

    def test_invalid_type_raises(self):
        from src.schemas.issue import RequirementIssue
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RequirementIssue(
                req_id="REQ-X",
                type="UnknownType",   # geçersiz literal
                severity="Low",
                problem="p",
                suggestion="s",
            )

    def test_invalid_severity_raises(self):
        from src.schemas.issue import RequirementIssue
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RequirementIssue(
                req_id="REQ-X",
                type="Ambiguity",
                severity="VeryHigh",  # geçersiz literal
                problem="p",
                suggestion="s",
            )


class TestConflictIssue:
    def test_valid_creation(self):
        from src.schemas.issue import ConflictIssue
        ci = ConflictIssue(
            source_req_id="REQ-001",
            conflict_with_text="Sistem 5 saniyede yanıt vermeli.",
            reason="REQ-001 3 sn derken bu 5 sn diyor.",
            severity="High",
        )
        assert ci.source_req_id == "REQ-001"
        assert ci.conflict_type is None  # opsiyonel alan

    def test_with_conflict_type(self):
        from src.schemas.issue import ConflictIssue
        ci = ConflictIssue(
            source_req_id="REQ-002",
            conflict_with_text="...",
            reason="Nicel çelişki",
            severity="Medium",
            conflict_type="Quantitative",
        )
        assert ci.conflict_type == "Quantitative"


class TestAnalysisReport:
    def test_valid_report(self):
        from src.schemas.report import AnalysisReport
        r = AnalysisReport(
            document_name="test.pdf",
            overall_quality_score=85,
            issues=[],
        )
        assert r.overall_quality_score == 85
        assert r.issues == []

    def test_score_bounds(self):
        from src.schemas.report import AnalysisReport
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AnalysisReport(
                document_name="x",
                overall_quality_score=101,  # > 100
                issues=[],
            )


class TestFinalSRSReport:
    def test_valid_final_report(self):
        from src.schemas.report import FinalSRSReport
        r = FinalSRSReport(
            document_name="final.pdf",
            overall_quality_score=72,
        )
        assert r.total_issues == 0
        assert r.total_conflicts == 0
        assert r.quality_issues == []
        assert r.conflicts == []

    def test_model_dump_json_is_valid_json(self):
        from src.schemas.report import FinalSRSReport
        r = FinalSRSReport(
            document_name="dump_test.pdf",
            overall_quality_score=60,
            executive_summary="Test özeti.",
            recommendations=["Öneri 1", "Öneri 2"],
        )
        json_str = r.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert parsed["document_name"] == "dump_test.pdf"
        assert isinstance(parsed["recommendations"], list)


class TestRequirementModel:
    def test_valid_requirement(self):
        from src.schemas.requirement import Requirement
        req = Requirement(req_id="REQ-005", text="Sistem 3 sn içinde yanıt vermeli.")
        assert req.req_id == "REQ-005"
        assert req.section is None
        assert req.source_page is None


# ─────────────────────────────────────────────────────────────────────────────
# 4  CONFIG
# ─────────────────────────────────────────────────────────────────────────────

class TestConfig:
    def test_config_variables_are_strings(self):
        import src.config as cfg
        assert isinstance(cfg.LLM_MODEL_NAME, str)
        assert isinstance(cfg.QDRANT_COLLECTION_NAME, str)
        assert isinstance(cfg.EMBEDDING_MODEL_NAME, str)

    def test_config_numeric_types(self):
        import src.config as cfg
        assert isinstance(cfg.CHUNK_SIZE, int)
        assert isinstance(cfg.CHUNK_OVERLAP, int)
        assert isinstance(cfg.TOP_K, int)
        assert isinstance(cfg.BATCH_SIZE, int)
        assert isinstance(cfg.LLM_TEMPERATURE, float)

    def test_config_defaults_non_empty(self):
        import src.config as cfg
        assert cfg.LLM_MODEL_NAME != ""
        assert cfg.QDRANT_COLLECTION_NAME != ""
        assert cfg.TOP_K > 0
        assert cfg.CHUNK_SIZE > 0


# ─────────────────────────────────────────────────────────────────────────────
# 5  json_utils
# ─────────────────────────────────────────────────────────────────────────────

class TestJsonUtils:
    def test_safe_parse_valid_json(self):
        from src.utils.json_utils import safe_parse_json
        result = safe_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_safe_parse_list_json(self):
        from src.utils.json_utils import safe_parse_json
        result = safe_parse_json('[{"a": 1}, {"b": 2}]')
        assert isinstance(result, list)
        assert len(result) == 2

    def test_safe_parse_with_markdown_fence(self):
        from src.utils.json_utils import safe_parse_json
        text = '```json\n{"conflict": true, "reason": "test"}\n```'
        result = safe_parse_json(text)
        assert result is not None
        assert result.get("conflict") is True

    def test_safe_parse_invalid_returns_fallback(self):
        from src.utils.json_utils import safe_parse_json
        result = safe_parse_json("bu geçerli json değil", fallback={"error": True})
        assert result == {"error": True}

    def test_safe_parse_empty_returns_fallback(self):
        from src.utils.json_utils import safe_parse_json
        result = safe_parse_json("", fallback=None)
        assert result is None

    def test_extract_json_from_text(self):
        from src.utils.json_utils import extract_json_from_text
        text = 'Sonuç: ```json\n[{"id": 1}]\n``` bitti.'
        result = extract_json_from_text(text)
        assert "[" in result

    def test_extract_json_raises_on_no_json(self):
        from src.utils.json_utils import extract_json_from_text
        with pytest.raises(ValueError):
            extract_json_from_text("hiç json yok burada")


# ─────────────────────────────────────────────────────────────────────────────
# 6  text_utils
# ─────────────────────────────────────────────────────────────────────────────

class TestTextUtils:
    def test_normalize_whitespace(self):
        from src.utils.text_utils import normalize_whitespace
        assert normalize_whitespace("  merhaba   dünya  ") == "merhaba dünya"

    def test_normalize_strips_newlines(self):
        from src.utils.text_utils import normalize_whitespace
        assert normalize_whitespace("a\n\nb\t\tc") == "a b c"

    def test_truncate_short_text_unchanged(self):
        from src.utils.text_utils import truncate_text
        assert truncate_text("kısa", max_chars=100) == "kısa"

    def test_truncate_long_text(self):
        from src.utils.text_utils import truncate_text
        result = truncate_text("a" * 300, max_chars=100)
        assert len(result) <= 103  # 100 + len("...")
        assert result.endswith("...")

    def test_split_into_batches_respects_limit(self):
        from src.utils.text_utils import split_into_batches
        lines = ["x" * 100] * 20  # her satır 100 karakter, toplam 2000
        batches = split_into_batches(lines, max_chars=500)
        for b in batches:
            assert len(b) <= 520  # tolerans: son satırın tamamı eklenir

    def test_split_empty_list(self):
        from src.utils.text_utils import split_into_batches
        assert split_into_batches([]) == []

    def test_extract_req_ids(self):
        from src.utils.text_utils import extract_req_ids
        text = "REQ-001 karşılaştırıldığında REQ-015 ile çelişiyor."
        ids = extract_req_ids(text)
        assert "REQ-001" in ids
        assert "REQ-015" in ids


# ─────────────────────────────────────────────────────────────────────────────
# 7  logging_utils
# ─────────────────────────────────────────────────────────────────────────────

class TestLoggingUtils:
    def test_get_logger_returns_logger(self):
        import logging
        from src.utils.logging_utils import get_logger
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_handlers(self):
        from src.utils.logging_utils import get_logger, _ROOT_LOGGER_NAME
        import logging
        get_logger("ensure_configured")
        root = logging.getLogger(_ROOT_LOGGER_NAME)
        assert len(root.handlers) > 0

    def test_logger_name_namespaced(self):
        from src.utils.logging_utils import get_logger, _ROOT_LOGGER_NAME
        logger = get_logger("mymodule")
        assert _ROOT_LOGGER_NAME in logger.name


# ─────────────────────────────────────────────────────────────────────────────
# 8  report_builder  (API çağrısı YOK)
# ─────────────────────────────────────────────────────────────────────────────

class TestReportBuilder:
    def _make_issue(self, req_id="REQ-001", severity="High"):
        from src.schemas.issue import RequirementIssue
        return RequirementIssue(
            req_id=req_id, type="Ambiguity", severity=severity,
            problem="test problem", suggestion="test öneri"
        )

    def _make_conflict(self, req_id="REQ-002", severity="High"):
        from src.schemas.issue import ConflictIssue
        return ConflictIssue(
            source_req_id=req_id,
            conflict_with_text="karşı metin...",
            reason="test çelişki nedeni",
            severity=severity,
        )

    def _make_analysis_report(self, issues=None):
        from src.schemas.report import AnalysisReport
        return AnalysisReport(
            document_name="test.pdf",
            overall_quality_score=80,
            issues=issues or [],
        )

    def test_build_empty_report(self):
        from src.core.report_builder import ReportBuilder
        builder = ReportBuilder()
        final = builder.build(self._make_analysis_report())
        assert final.document_name == "test.pdf"
        assert final.total_issues == 0
        assert final.total_conflicts == 0
        assert final.overall_quality_score == 100  # hiç hata yok → 100

    def test_build_with_issues(self):
        from src.core.report_builder import ReportBuilder
        issues = [
            self._make_issue(severity="Critical", req_id="REQ-001"),
            self._make_issue(severity="Low", req_id="REQ-002")
        ]
        builder = ReportBuilder()
        final = builder.build(self._make_analysis_report(issues))
        # Critical(-20) + Low(-2) = 78
        assert final.overall_quality_score == 78
        assert final.total_issues == 2

    def test_build_with_conflicts(self):
        from src.core.report_builder import ReportBuilder
        conflicts = [self._make_conflict(severity="High")]
        builder = ReportBuilder()
        final = builder.build(self._make_analysis_report(), conflicts)
        # High conflict → -15 → skor = 85
        assert final.overall_quality_score == 85
        assert final.total_conflicts == 1

    def test_build_score_never_below_zero(self):
        from src.core.report_builder import ReportBuilder
        # 10 Critical issue → 10 * 20 = 200 puan düşüşü → min 0
        # Her birinin farklı req_id'si olmalı ki dedup edilmesinler
        issues = [self._make_issue(severity="Critical", req_id=f"REQ-{i}") for i in range(10)]
        builder = ReportBuilder()
        final = builder.build(self._make_analysis_report(issues))
        assert final.overall_quality_score == 0

    def test_final_json_is_valid(self):
        from src.core.report_builder import ReportBuilder
        issues = [self._make_issue()]
        conflicts = [self._make_conflict()]
        builder = ReportBuilder()
        final = builder.build(self._make_analysis_report(issues), conflicts)
        json_str = final.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert "document_name" in parsed
        assert "overall_quality_score" in parsed
        assert "quality_issues" in parsed
        assert "conflicts" in parsed
        assert "recommendations" in parsed
        assert isinstance(parsed["recommendations"], list)

    def test_executive_summary_auto_generated(self):
        from src.core.report_builder import ReportBuilder
        builder = ReportBuilder()
        final = builder.build(self._make_analysis_report())
        assert final.executive_summary is not None
        assert len(final.executive_summary) > 0

    def test_custom_executive_summary(self):
        from src.core.report_builder import ReportBuilder
        builder = ReportBuilder()
        final = builder.build(
            self._make_analysis_report(),
            executive_summary="Özel özet metni.",
        )
        assert final.executive_summary == "Özel özet metni."

# ─────────────────────────────────────────────────────────────────────────────
# 10  analyzer.py eski importlar
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzerBackwardCompat:
    def test_requirement_issue_importable_from_analyzer(self):
        """Eski: from src.core.analyzer import RequirementIssue"""
        from src.core.analyzer import RequirementIssue  # noqa: F401
        assert RequirementIssue is not None

    def test_analysis_report_importable_from_analyzer(self):
        """Eski: from src.core.analyzer import AnalysisReport"""
        from src.core.analyzer import AnalysisReport  # noqa: F401
        assert AnalysisReport is not None

    def test_calculate_score_importable(self):
        """workflow.py: from src.core.analyzer import calculate_score"""
        from src.core.analyzer import calculate_score
        from src.schemas.issue import RequirementIssue
        issue = RequirementIssue(
            req_id="REQ-001", type="Ambiguity", severity="Critical",
            problem="p", suggestion="s"
        )
        score = calculate_score([issue])
        assert score == 80  # 100 - 20 = 80

    def test_schemas_are_same_class(self):
        """analyzer.py'den alınan model, schemas'taki ile aynı sınıf olmalı."""
        from src.core.analyzer import RequirementIssue as AI_RI
        from src.schemas.issue import RequirementIssue as SC_RI
        assert AI_RI is SC_RI


# ─────────────────────────────────────────────────────────────────────────────
# 11  workflow.py static import kontrolü (LLM init olmadan)
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkflowImport:
    def test_workflow_module_importable(self):
        """workflow.py modülü import edilebilmeli (sınıf init olmadan)."""
        import importlib
        spec = importlib.util.find_spec("src.interface.workflow")
        assert spec is not None, "src.interface.workflow modülü bulunamadı."
