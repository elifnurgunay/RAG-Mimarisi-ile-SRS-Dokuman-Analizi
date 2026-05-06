import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

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

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# .env yükle
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

class ConflictDetector:
    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY")
        )
        self.parser = JsonOutputParser()

    def analyze_conflict(self, req1: str, req2: str) -> dict:
        """İki gereksinim arasındaki çelişkiyi analiz eder."""
        
        prompt_template = """
Sen uzman bir Yazılım Gereksinim Analistisin. Aşağıdaki iki gereksinim maddesini karşılaştır ve aralarında bir ÇELİŞKİ (Conflict) veya Tutarsızlık olup olmadığını belirle.

**Gereksinim 1:** {req1}
**Gereksinim 2:** {req2}

**Analiz Rehberi - Aşağıdakilerden BİRİ bile varsa "conflict": true döndür:**
- **Nicel Çelişkiler:** Aynı konu hakkında farklı sayısal değerler (Örn: "max 10 kullanıcı" vs "en az 1000 kullanıcı", "30 gün sakla" vs "1 hafta sonra sil").
- **Mantıksal Çelişkiler:** Bir madde bir şeyi zorunlu kılarken diğerinin yasaklaması (Örn: "veriler şifrelenmeli" vs "veriler şifrelenmemeli").
- **Platform/Ortam Çelişkileri:** Farklı platformlar veya ağ ortamları belirtilmesi (Örn: "sadece iOS" vs "sadece Android", "sadece intranet" vs "genel internet").
- **Görsel/Tasarım Çelişkileri:** Aynı öğe için farklı değerler (Örn: "mavi tema" vs "kırmızı tema").
- **Format Çelişkileri:** Aynı çıktı için farklı formatlar (Örn: "sadece Excel" vs "sadece PDF").
- **Süre/Zaman Çelişkileri:** Aynı veri için farklı saklama süreleri (Örn: "30 gün sakla" vs "1 hafta sonra sil").

**Kurallar:**
1. İki madde aynı konudan bahsediyorsa ve farklı/zıt değerler veriyorsa, bu MUTLAKA bir çelişkidir.
2. "Sadece X" ifadesi varsa ve diğer madde "sadece Y" diyorsa, bu bir çelişkidir.
3. Eğer iki madde tamamen farklı konulardan bahsediyorsa (ilişkisiz), o zaman false döndür.
4. "reason" kısmında hangi maddelerin neden birbiriyle uyuşmadığını detaylandır.

Yanıtı SADECE şu JSON formatında ver:
{{
    "conflict": boolean,
    "reason": "string",
    "severity": "Low/Medium/High"
}}
"""
        
        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm | self.parser

        try:
            result = chain.invoke({"req1": req1, "req2": req2})
            return result
        except Exception as e:
            return {"conflict": False, "reason": f"Hata: {str(e)}", "severity": "None"}

if __name__ == "__main__":
    detector = ConflictDetector()
    
    # GÜN 3 TESTİ: Çelişki Bulma
    r1 = "Sistem verileri 30 gun saklamalidir."
    r2 = "Veriler 1 hafta sonra kalici olarak silinmelidir."
    
    print("Analiz ediliyor...")
    result = detector.analyze_conflict(r1, r2)
    print(f"Sonuc: {result}")
