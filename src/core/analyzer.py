import sys
import os 
from typing import List, Literal

# --- SIHIRLI DOKUNUŞ V2: Python 3.14 Yaması ---
class DummyClass:
    pass
class MockModule:
    def __getattr__(self, name): return DummyClass  
    def __call__(self, *args, **kwargs): return DummyClass()
sys.modules['pydantic.v1'] = MockModule()
sys.modules['pydantic.v1.errors'] = MockModule()
sys.modules['pydantic.v1.main'] = MockModule()
sys.modules['pydantic.v1.fields'] = MockModule()
sys.modules['pydantic.v1.validators'] = MockModule()
# --------------------------------------------------

from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

# .env dosyasındaki API anahtarını yükler
load_dotenv(override=True)

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

    def run_analysis(self, chunk_text: str, metadata: dict = None) -> AnalysisReport:
        """Tek bir chunk için analiz çalıştırır."""
        return self.analyze_text(chunk_text, doc_name="Chunk", metadata=metadata)

    def analyze_text(self, srs_text: str, doc_name: str = "Doküman", metadata: dict = None) -> AnalysisReport:
        """
        Gereksinimleri mantıksal batch'lere bölerek analiz eder.
        Rate limit yönetimi ve toplu işleme ile API maliyetini düşürür.
        """
        # Metni satırlara böl (Gereksinim bazlı batching için)
        lines = [line.strip() for line in srs_text.split("\n") if line.strip()]
        
        # Her batch'te yaklaşık 5-10 gereksinim olacak şekilde grupla (Max 5000 karakter)
        batches = []
        current_batch = []
        current_length = 0
        
        for line in lines:
            if current_length + len(line) > 5000 and current_batch:
                batches.append("\n".join(current_batch))
                current_batch = []
                current_length = 0
            current_batch.append(line)
            current_length += len(line)
        
        if current_batch:
            batches.append("\n".join(current_batch))
        
        all_issues = []
        import time
        import random
        
        prompt_template = """
Sen kıdemli bir Yazılım Gereksinim Mühendisisin. Aşağıdaki SRS metin parçalarını ISO/IEC/IEEE 29148 standartlarına göre analiz et.

**Analiz Kriterleri:** Belirsizlik (Ambiguity), Çelişki (Inconsistency), Eksiklik (Incompleteness), Test Edilebilirlik (Testability).

**Görevin:** Verilen metindeki TÜM hataları tespit et ve her biri için somut düzeltme önerisi sun.
**Önemli:** Eğer bir satırda birden fazla hata varsa hepsini raporla. 'req_id' alanını mutlaka doldur (metinde yoksa metadatayı kullan).

Analiz Edilecek Metin:
{chunk_text}

Metadata: {metadata}

Çıktıyı SADECE JSON formatında ver:
{format_instructions}
"""
        prompt = ChatPromptTemplate.from_template(prompt_template).partial(
            format_instructions=self.parser.get_format_instructions()
        )
        chain = prompt | self.llm

        for i, chunk in enumerate(batches):
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    print(f"--- [BATCH {i+1}/{len(batches)}] Analiz Ediliyor (Deneme {retry_count+1})... ---")
                    raw_output = chain.invoke({"chunk_text": chunk, "metadata": metadata or {}})
                    parsed_data = self.parser.parse(raw_output.content)

                    issues = []
                    if isinstance(parsed_data, dict):
                        issues = parsed_data.get("issues", [])
                    elif hasattr(parsed_data, "issues"):
                        issues = parsed_data.issues
                    
                    for issue_data in issues:
                        if isinstance(issue_data, dict):
                            all_issues.append(RequirementIssue(**issue_data))
                        else:
                            all_issues.append(issue_data)
                    
                    # Başarılı ise döngüden çık
                    break
                    
                except Exception as e:
                    if "rate_limit_exceeded" in str(e).lower() or "429" in str(e):
                        wait_time = (2 ** retry_count) * 5 + random.random()
                        print(f"⚠️ Hız sınırına takılındı. {wait_time:.1f} sn bekleniyor...")
                        time.sleep(wait_time)
                        retry_count += 1
                    else:
                        print(f"!!! [BATCH {i+1}] HATASI: {e}")
                        break
            
            # Batch'ler arası kısa bekleme (Groq RPM koruması)
            time.sleep(2)

        report_obj = AnalysisReport(
            document_name=doc_name,
            overall_quality_score=calculate_score(all_issues),
            issues=all_issues
        )
        return report_obj

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