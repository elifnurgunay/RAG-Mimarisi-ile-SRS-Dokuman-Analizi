"""
src/core/analyzer.py

LLM tabanlı SRS kalite analiz motoru.
Model nesneleri src/schemas/ içinde, LLM src/core/llm_client.py üzerinden alınır.
"""
import os
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser


# Merkezi modüller
from src.core.llm_client import get_llm
from src.schemas.issue import RequirementIssue
from src.schemas.report import AnalysisReport
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

# RequirementIssue ve AnalysisReport artık src/schemas/ altında tanımlı.
# Geriye dönük uyumluluk için burada da dışa aktarılıyor.
__all__ = ["RequirementIssue", "AnalysisReport", "calculate_score", "SRSAnalyzer"]

# --- YARDIMCI FONKSİYON ---
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
        # LLM merkezi fabrikadan alınıyor (src/core/llm_client.py)
        self.llm = get_llm()
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
            if current_length + len(line) > 50000 and current_batch:
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
Sen kıdemli bir Yazılım Gereksinim Mühendisisin. Aşağıdaki SRS (Yazılım Gereksinim Spesifikasyonu) metin parçalarını analiz et.

**Kritik Talimatlar:**
1. **Sadece Mevcut Metne Odaklan:** Metinde açıkça yazmayan bölümler için (örn: "Giriş bölümü eksik", "Proje önerisi yok") gibi halüsinasyonlar üretme. Sadece elindeki metin parçasındaki hataları raporla.
2. **Başlıkları ve Şekil Yazılarını Atla:** Eğer bir satır sadece bir başlık (örn: "4. Kısıtlar") veya şekil adı (örn: "Şekil 5: Diyagram") ise, bunu bir gereksinim maddesi olarak görme ve hata raporlama.
3. **Somut Hataları Bul:** Belirsizlik (Ambiguity), Çelişki (Inconsistency), Eksiklik (Maddenin kendi içindeki eksiklik) ve Test Edilebilirlik (Testability) kriterlerine odaklan.
4. **Kesin Kanıt:** Her hata için "Problem" kısmında metindeki hangi ifadenin neden hatalı olduğunu açıklat.

**Giriş Metni:**
{chunk_text}

**Metadata:** {metadata}

Yanıtını SADECE AnalysisReport şemasına uygun JSON formatında ver.
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
                    logger.info(
                        "Batch analiz ediliyor | batch=%d/%d | deneme=%d",
                        i + 1,
                        len(batches),
                        retry_count + 1,
                    )

                    raw_output = chain.invoke({
                        "chunk_text": chunk,
                        "metadata": metadata or {},
                    })
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

                    break

                except Exception as e:
                    if "rate_limit_exceeded" in str(e).lower() or "429" in str(e):
                        wait_time = (2 ** retry_count) * 5 + random.random()
                        logger.warning("Rate limit | bekleme=%.1f sn", wait_time)
                        time.sleep(wait_time)
                        retry_count += 1
                    else:
                        logger.error(
                            "Batch analizi hatası | batch=%d | hata=%s",
                            i + 1,
                            e,
                        )
                        break

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