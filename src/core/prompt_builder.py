# src/core/prompt_builder.py

from langchain_core.prompts import ChatPromptTemplate


class PromptBuilder:
    def build_analysis_prompt(self, format_instructions: str):
        prompt_template = """
You are a senior Software Requirements Engineer. Analyze the following SRS (Software Requirements Specification) text chunks.

**OUTPUT LANGUAGE RULE:**
- Detect the dominant language of the input SRS text.
- Write all human-readable analysis fields in the same language as the input SRS.
- If the SRS is in English, write `problem`, `suggestion`, summaries, and recommendations in English.
- If the SRS is in Turkish, write `problem`, `suggestion`, summaries, and recommendations in Turkish.
- Do not mix Turkish and English in the same explanation unless the original requirement contains technical terms.
- Keep JSON keys exactly as required by the schema.
- Keep enum values exactly as required by the schema.

**Critical Instructions:**
1. **Use only the given text:** Do not infer problems that are not explicitly supported by the text.
2. **Ignore headings and captions:** Do not treat section titles, table titles, figure captions, page numbers, or layout artifacts as requirements.
3. **Report concrete issues only:** Report only clear ambiguity, incompleteness, inconsistency, or testability problems.
4. **Require direct evidence:** Every issue must be supported by direct evidence from the input text. If there is no evidence, do not create an issue.
5. **Do not confuse semantic relation with contradiction:** Two requirements being related to the same domain does not automatically mean they conflict.
6. **Report only direct logical contradictions:** A conflict exists only when two requirements cannot both be true at the same time.
7. **Do not mark supportive or compatible requirements as conflicts.**
8. **Duplicate is not a conflict:** Similar or repeated requirements should be reported as quality issues, not as conflicts.
9. **Do not report security + encryption as conflict.**
10. **Do not report cloud + internet access as conflict.**
11. **Do not report modern UI + mobile app as conflict.**
12. **Classify duplicates correctly:** If a requirement duplicates another requirement, classify it as `Inconsistency`, not `Incompleteness`.

**Input Text:**
{chunk_text}

**Metadata:** {metadata}

Duplicate example:
- problem: "REQ-008 duplicates REQ-002."
- type: "Inconsistency"
- suggestion: "Remove REQ-008 or consolidate it with REQ-002." 

Return ONLY valid JSON matching the AnalysisReport schema.
{format_instructions}
"""
        return ChatPromptTemplate.from_template(prompt_template).partial(
            format_instructions=format_instructions
        )