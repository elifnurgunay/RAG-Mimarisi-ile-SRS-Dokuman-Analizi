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

    def run_analysis(self, chunk_text: str, metadata: dict = None) -> AnalysisReport:
        """Tek bir chunk için analiz çalıştırır."""
        return self.analyze_text(chunk_text, doc_name="Chunk", metadata=metadata)

    def analyze_text(self, srs_text: str, doc_name: str = "Doküman", metadata: dict = None) -> AnalysisReport:
        """
        Büyük metinleri parçalara ayırarak analiz eder ve sonuçları birleştirir.
        (Token limitini aşmamak için batch processing yapar)
        """
        # Yaklaşık 4000 karakterlik parçalara böl (Daha güvenli sınır)
        max_chars = 4000
        text_chunks = [srs_text[i:i+max_chars] for i in range(0, len(srs_text), max_chars)]
        
        all_issues = []
        import time
        
        prompt_template = """
Sen dünya çapında tanınan kıdemli bir Yazılım Gereksinim Mühendisisin. Görevin, verilen SRS (Yazılım Gereksinim Belgesi) metnini ISO/IEC/IEEE 29148 standartlarına göre titizlikle analiz etmektir.

Analiz Kriterlerin:
1. **Ambiguity (Belirsizlik)**: "Hızlı", "esnek", "yeterli", "kullanıcı dostu", "gerektiğinde" gibi sübjektif ve ölçülemeyen ifadeler. Her gereksinim tek bir şekilde yorumlanabilmelidir.
2. **Inconsistency (Çelişki)**: Bir gereksinimin başka bir gereksinimle, teknik kısıtla veya iş mantığıyla çelişmesi.
3. **Incompleteness (Eksiklik)**: Gereksinimde 'kim', 'ne zaman', 'nerede' veya 'nasıl' sorularından birinin cevapsız kalması. Özellikle aktör (sistem mi, kullanıcı mı?) belirtilmemiş maddeler.
4. **Testability (Test Edilebilirlik)**: Gereksinimin doğrulanması için somut bir test kriterinin yazılamaması. Sayısal değer içermeyen performans veya kapasite hedefleri.
5. **Redundancy (Gereksiz Tekrar)**: Aynı gereksinimin farklı kelimelerle birden fazla kez ifade edilmesi.

Kurallar:
- Metni SATIR SATIR incele. 
- Sadece bariz hataları değil, ileride geliştirme ekibine sorun çıkarabilecek potansiyel "gri alanları" da raporla.
- Sorun tespit ettiysen teknik, profesyonel ve yapıcı bir dil kullan.
- 'suggestion' kısmında mutlaka bu gereksinimin nasıl daha iyi yazılabileceğine dair somut bir örnek ver.
- overall_quality_score (0-100): Dokümanın genel kalitesini yansıtmalıdır. Kritik hatalar puanı hızla düşürmelidir.

GÖREVİN: Sana verilen gereksinim metnini analiz et.

ÖNEMLİ İZLENEBİLİRLİK KURALI:
Tespit ettiğin her hata, çelişki veya bulgu için JSON çıktısında MUTLAKA bir 'req_id' belirtmek zorundasın. 
1. Eğer metnin içinde açık bir gereksinim ID'si (örn: REQ-001) varsa onu kullan.
2. Eğer açık bir ID yoksa, sana sağlanan metadatadaki 'req_id' değerini (örn: AUTO-1-5) kullan.
3. Asla 'ID-YOK', 'Bilinmiyor' veya 'Yok' gibi jenerik ifadeler kullanma. 
4. 'req_id' alanını asla boş bırakma.

Analiz Edilecek Metin:
{chunk_text}

Metadata:
{metadata}

Çıktıyı SADECE şu JSON formatında ver:
{format_instructions}
"""
        
        prompt = ChatPromptTemplate.from_template(prompt_template).partial(
            format_instructions=self.parser.get_format_instructions()
        )
        
        chain = prompt | self.llm

        for i, chunk in enumerate(text_chunks):
            try:
                print(f"--- [BATCH {i+1}/{len(text_chunks)}] LLM Analizi Yapılıyor... ---")
                raw_output = chain.invoke({"chunk_text": chunk, "metadata": metadata or {}})
                parsed_data = self.parser.parse(raw_output.content)

                # Pydantic objesi veya dict kontrolü
                issues = []
                if isinstance(parsed_data, dict):
                    issues = parsed_data.get("issues", [])
                elif hasattr(parsed_data, "issues"):
                    issues = parsed_data.issues
                
                # Her issue'yu RequirementIssue modeline çevir (güvenlik için)
                for issue_data in issues:
                    if isinstance(issue_data, dict):
                        all_issues.append(RequirementIssue(**issue_data))
                    else:
                        all_issues.append(issue_data)
                        
            except Exception as e:
                print(f"!!! [BATCH {i+1}] HATASI: {e}")
                
            # RPM limitine takılmamak için kısa bir mola
            if len(text_chunks) > 1:
                time.sleep(1)

        # Raporu birleştir
        report_obj = AnalysisReport(
            document_name=doc_name,
            overall_quality_score=0,
            issues=all_issues
        )
        
        # Skoru en son tüm hatalar üzerinden hesapla
        report_obj.overall_quality_score = calculate_score(report_obj.issues)
        
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