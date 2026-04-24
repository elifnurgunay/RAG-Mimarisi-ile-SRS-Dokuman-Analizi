import os 
from typing import List, Literal
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

# .env dosyasındaki API anahtarını yükler
load_dotenv()

# --- VERİ ŞEMASI (PYDANTIC) ---
class RequirementIssue(BaseModel):
    req_id: str = Field(..., description="Analiz edilen gereksinimin ID'si")
    type: Literal["Ambiguity", "Inconsistency", "Incompleteness", "Testability"] = Field(..., description="Hata tipi")
    severity: Literal["Critical", "High", "Medium", "Low"] = Field(..., description="Ciddiyet seviyesi")
    problem: str = Field(..., description="Tespit edilen sorunun teknik açıklaması")
    suggestion: str = Field(..., description="Düzeltme önerisi")

class AnalysisReport(BaseModel):
    document_name: str
    overall_quality_score: int
    issues: List[RequirementIssue]

def calculate_score(issues: List[RequirementIssue]) -> int:
    score = 100
    weights = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
    for issue in issues:
        score -= weights.get(issue.severity, 0)
    return max(0, score)

# --- ANALİZ MOTORU SINIFI ---
class SRSAnalyzer:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Hata: .env dosyasında GROQ_API_KEY bulunamadı!")
            
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            groq_api_key=api_key
        )
        self.parser = JsonOutputParser(pydantic_object=AnalysisReport)

    def analyze_text(self, srs_text: str, doc_name: str = "Doküman") -> AnalysisReport:
        prompt_template = """
Sen uzman bir Yazılım Gereksinim Mühendisisin ve ISO/IEC/IEEE 29148 standardına göre analiz yapıyorsun.

Görevin:
Verilen gereksinimleri DERİNLEMESİNE incele ve SADECE açıkça tespit edilebilir sorunları raporla.

Analiz Kriterleri:

1. Ambiguity:
- Belirsiz kelimeler: "hızlı", "iyi", "kullanıcı dostu"
- Ölçülemeyen ifadeler

2. Inconsistency:
- Birbiriyle çelişen gereksinimler
- Farklı yerlerde farklı değerler

3. Incompleteness:
- Eksik bilgi (kim? ne zaman? nasıl?)
- Edge case eksiklikleri

4. Testability:
- Test edilemeyen gereksinimler
- Ölçü kriteri olmayan ifadeler

Kurallar:
- Her issue için mutlaka req_id belirt
- Eğer sorun yoksa boş liste döndür (uydurma!)
- Teknik ve net yaz
- Genelleme yapma

overall_quality_score hesaplama:
- Başlangıç: 100
- Critical: -20
- High: -10
- Medium: -5
- Low: -2
- Minimum skor: 0

--- ANALİZ EDİLECEK METİN ---
{srs_text}

Çıktıyı SADECE şu JSON formatında ver:
{format_instructions}
"""
        
        prompt = ChatPromptTemplate.from_template(prompt_template).partial(
            format_instructions=self.parser.get_format_instructions()
        )
        
        chain = prompt | self.llm

        try:
            raw_output = chain.invoke({"srs_text": srs_text})
            return self.parser.parse(raw_output.content)
        except Exception as e:
            print(f"Analiz Hatası: {e}")
            return None

    def analyze_text_with_score(self, srs_text: str, doc_name: str = "Doküman") -> AnalysisReport:
        prompt_template = """
Sen uzman bir Yazılım Gereksinim Mühendisisin ve ISO/IEC/IEEE 29148 standardına göre analiz yapıyorsun.

--- ANALİZ EDİLECEK METİN ---
{srs_text}

Çıktıyı SADECE şu JSON formatında ver:
{format_instructions}
"""

        prompt = ChatPromptTemplate.from_template(prompt_template).partial(
            format_instructions=self.parser.get_format_instructions()
        )

        chain = prompt | self.llm

        try:
            raw_output = chain.invoke({"srs_text": srs_text})

            # 1. Parse
            parsed_data = self.parser.parse(raw_output.content)

            # 2. dict ise objeye çevir (HATA FIX)
            if isinstance(parsed_data, dict):
                parsed_data = AnalysisReport(**parsed_data)

            parsed_data.document_name = doc_name

            # 3. Skoru Python ile hesapla
            parsed_data.overall_quality_score = calculate_score(parsed_data.issues)

            return parsed_data

        except Exception as e:
            print(f"Analiz Hatası: {e}")
            return None


# --- TEST ETME ---
if __name__ == "__main__":
    analyzer = SRSAnalyzer()
    
    test_text = """
    REQ-001: Sistem çok hızlı olmalı.
    REQ-002: Kullanıcı verileri 2 yıl saklanmalı.
    REQ-003: Sistem kullanıcı dostu olmalı.
    """
    
    result = analyzer.analyze_text_with_score(test_text)
    print(result)