# src/core/analysis_engine.py

import time
from typing import List

from langchain_core.output_parsers import JsonOutputParser

from src.core.prompt_builder import PromptBuilder
from src.schemas.issue import RequirementIssue
from src.schemas.report import AnalysisReport
from src.utils.logging_utils import get_logger
from src.utils.retry_utils import RetryPolicy

logger = get_logger(__name__)


class AnalysisEngine:
    def __init__(self, llm, parser: JsonOutputParser | None = None):
        self.llm = llm
        self.parser = parser or JsonOutputParser(pydantic_object=AnalysisReport)
        self.prompt_builder = PromptBuilder()
        self.batch_delay_seconds = 2.0
        self.retry_policy = RetryPolicy(
            max_retries=3,
            base_delay=5.0,
            backoff_factor=2.0,
            jitter=True,
        )

    def analyze_batches(
        self,
        batches: List[str],
        metadata: dict | None = None,
    ) -> List[RequirementIssue]:
        all_issues: List[RequirementIssue] = []

        prompt = self.prompt_builder.build_analysis_prompt(
            self.parser.get_format_instructions()
        )
        chain = prompt | self.llm

        for i, chunk in enumerate(batches):
            issues = self._analyze_single_batch(
                chain=chain,
                chunk=chunk,
                metadata=metadata,
                batch_index=i,
                total_batches=len(batches),
            )
            all_issues.extend(issues)

            time.sleep(self.batch_delay_seconds)

        return all_issues

    def _analyze_single_batch(
        self,
        chain,
        chunk: str,
        metadata: dict | None,
        batch_index: int,
        total_batches: int,
    ) -> List[RequirementIssue]:
        def operation():
            logger.info(
                "Batch analiz ediliyor | batch=%d/%d",
                batch_index + 1,
                total_batches,
            )

            raw_output = chain.invoke(
                {
                    "chunk_text": chunk,
                    "metadata": metadata or {},
                }
            )
            parsed_data = self.parser.parse(raw_output.content)

            return self._extract_issues(parsed_data)

        try:
            return self.retry_policy.run(
                operation=operation,
                operation_name=f"analysis_batch_{batch_index + 1}",
            )
        except Exception as exc:
            logger.error(
                "Batch analizi başarısız | batch=%d | hata=%s",
                batch_index + 1,
                exc,
            )
            return []

    def _extract_issues(self, parsed_data) -> List[RequirementIssue]:
        issues = []

        if isinstance(parsed_data, dict):
            issues = parsed_data.get("issues", [])
        elif hasattr(parsed_data, "issues"):
            issues = parsed_data.issues

        result = []
        for issue_data in issues:
            if isinstance(issue_data, dict):
                result.append(RequirementIssue(**issue_data))
            else:
                result.append(issue_data)

        return result