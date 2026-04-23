import os
from typing import List, Literal
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

load_dotenv()

# --- PYDANTIC MODELS ---

class RequirementIssue(BaseModel):
    req_id: str = Field(...)
    type: Literal["Ambiguity", "Inconsistency", "Incompleteness", "Testability"]
    severity: Literal["Critical", "High", "Medium", "Low"]
    problem: str
    suggestion: str


class SRSAnalysisReport(BaseModel):
    document_overview: str
    overall_quality_score: int = Field(ge=0, le=100)
    issues: List[RequirementIssue] = []


# --- ANALYZER ---

class SRSAnalyzer:
    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            groq_api_key=os.getenv("GROQ_API_KEY")
        )

        self.parser = JsonOutputParser(pydantic_object=SRSAnalysisReport)

        system_instruction = """
Sen uzman bir Yazılım Gereksinim Mühendisisin.
ISO/IEC/IEEE 29148 standardına göre analiz yap.

Kurallar:
- Sadece JSON döndür
- Açıklama yazma
- Sohbet etme

{format_instructions}
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_instruction),
            ("human", "Analiz edilecek gereksinim:\n\n{srs_text}")
        ]).partial(
            format_instructions=self.parser.get_format_instructions()
        )

        self.chain = prompt | self.llm | self.parser

    def analyze(self, text: str):
        print("DEBUG: analyze başladı")

        try:
            result = self.chain.invoke({"srs_text": text})
            print("DEBUG: API cevap geldi")
            return result

        except Exception as e:
            print("HATA:", e)
            return None


# --- TEST ---

if __name__ == "__main__":
    analyzer = SRSAnalyzer()

    sample_text = """
    REQ-001: Sistem çok hızlı olmalıdır.
    REQ-002: Veriler 2 yıl saklanmalıdır.
    """

    report = analyzer.analyze(sample_text)
    print(report)