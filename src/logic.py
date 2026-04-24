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
        Sen uzman bir Yazılım Gereksinim Analistisin. 
        Aşağıdaki iki gereksinim maddesini karşılaştır ve aralarında bir ÇELİŞKİ (Conflict) olup olmadığını belirle.
        
        Gereksinim 1: {req1}
        Gereksinim 2: {req2}
        
        Kurallar:
        1. Eğer iki madde birbiriyle doğrudan veya dolaylı olarak çelişiyorsa "conflict": true döndür.
        2. Çelişki yoksa "conflict": false döndür.
        3. "reason" kısmında teknik bir açıklama yap.
        
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
