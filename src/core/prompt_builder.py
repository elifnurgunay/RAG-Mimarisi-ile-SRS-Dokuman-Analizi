# src/core/prompt_builder.py

from langchain_core.prompts import ChatPromptTemplate


class PromptBuilder:
    def build_analysis_prompt(self, format_instructions: str):
        prompt_template = """
You are a senior Software Requirements Engineer. Carefully analyze the following SRS (Software Requirements Specification) text.

**OUTPUT LANGUAGE RULE:**
- Detect the dominant language of the input SRS text.
- Write all human-readable fields (`problem`, `suggestion`) in the same language as the SRS.
- Keep JSON keys and enum values exactly as required by the schema.

**STRICT ANALYSIS RULES:**
1. **MANDATORY EXHAUSTIVE EXTRACTION:** You MUST extract every single error. Do not stop at a few examples.
   - STEP 1: Scan the text to identify ALL requirement IDs (e.g., FR-01, NFR-02).
   - STEP 2: Evaluate EACH requirement one by one against the issue types below.
   - STEP 3: If a requirement has an issue, you MUST add it to the JSON. Do not skip any defective requirement.
2. **Read the actual text carefully.** Every issue you report MUST be directly supported by a specific phrase or sentence from the input text below. Quote or reference it.
2. **Use the actual requirement IDs from the text.** Only report issues for requirement IDs that actually appear in the input (e.g., FR-01, NFR-03, REQ-5). Do NOT invent or guess IDs.
3. **Report only real problems found in THIS specific document.** Do not use generic or templated problems.
4. **Issue types to look for:**
   - `Ambiguity`: Vague terms like "fast", "user-friendly", "appropriate", "some", "several", "periodically" without measurable criteria.
   - `Incompleteness`: Missing actors, error handling, conditions, or acceptance criteria for a specific requirement.
   - `Inconsistency`: Two requirements that directly contradict each other, or a requirement that duplicates another.
   - `Testability`: A requirement with no measurable or verifiable acceptance criterion.
5. **Do NOT report:** headings, page numbers, section titles, table captions, or any non-requirement text.
6. **Do NOT report** issues that are not clearly evidenced in the text.
7. **Severity:** Use `High` for critical functional gaps, `Medium` for moderate quality issues, `Low` for minor wording issues.

**Input SRS Text:**
{chunk_text}

**Metadata:** {metadata}

Return ONLY valid JSON matching the AnalysisReport schema. Do not include any text outside the JSON.
{format_instructions}
"""
        return ChatPromptTemplate.from_template(prompt_template).partial(
            format_instructions=format_instructions
        )