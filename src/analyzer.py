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

# --- YARDIMCI FONKSİYONLAR ---
def calculate_score(issues: List[RequirementIssue]) -> int:
    """Hataların ciddiyetine göre 100 üzerinden kalite puanı hesaplar."""
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
            temperature=0.0,  # Deterministik çıktı
            groq_api_key=api_key
        )
        self.parser = JsonOutputParser(pydantic_object=AnalysisReport)

    def analyze_text(self, srs_text: str, doc_name: str = "Doküman") -> AnalysisReport:
        """
        SRS metnini analiz eder ve sonucu AnalysisReport nesnesi olarak döner.
        """
        prompt_template = """
Sen uzman bir Yazılım Gereksinim Mühendisisin ve ISO/IEC/IEEE 29148 standardına göre analiz yapıyorsun.

Görevin:
Verilen gereksinimleri DERİNLEMESİNE incele ve SADECE açıkça tespit edilebilir sorunları raporla.

Analiz Kriterleri:
1. Ambiguity: Ölçülemeyen ifadeler (hızlı, iyi vb.)
2. Inconsistency: Birbiriyle çelişen gereksinimler
3. Incompleteness: Eksik bilgi veya aktör eksikliği
4. Testability: Test edilemeyen/ölçülemeyen gereksinimler

Kurallar:
- Her issue için mutlaka req_id belirt (Metinde ID yoksa 'ID-YOK' yaz).
- Eğer sorun yoksa 'issues' listesini boş döndür.
- Teknik ve net yaz.
- overall_quality_score'u hesaplarken her hatayı ciddiyetine göre değerlendir.

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
            # 1. LLM Yanıtını Al
            raw_output = chain.invoke({"srs_text": srs_text})
            
            # 2. Ham metni sözlüğe (dict) çevir
            parsed_data = self.parser.parse(raw_output.content)

            # 3. SÖZLÜĞÜ NESNEYE ÇEVİR 
            if isinstance(parsed_data, dict):
                report_obj = AnalysisReport(**parsed_data)
            else:
                report_obj = parsed_data

            # 4. Profesyonel Skorlama ve Metadata Güncelleme
            report_obj.document_name = doc_name
            report_obj.overall_quality_score = calculate_score(report_obj.issues)
            
            return report_obj

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
    
    result = analyzer.analyze_text(test_text, "Test_Gereksinimleri")
    print(f"Puan: {result.overall_quality_score}")
    print(f"Hatalar: {result.issues}")