import sys
import os
from pathlib import Path
from retriever import SRSRetriever
from logic import ConflictDetector

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

class SRSWorkflow:
    def __init__(self):
        self.retriever = SRSRetriever(collection_name="main_workflow_collection")
        self.detector = ConflictDetector()

    def process_and_analyze(self, pdf_path: str, query_requirement: str):
        """Tum akisi yonetir: PDF Yukle -> Benzerleri Bul -> Celiski Analizi Yap"""
        
        print(f"\n--- Akis Baslatildi: {pdf_path} ---")
        
        # 1. PDF'i yukle ve indexle
        if not self.retriever.load_and_index_pdf(pdf_path):
            return "PDF yukleme hatasi."

        # 2. Benzer gereksinimleri getir (Arama)
        print(f"\nBenzer maddeler araniyor: '{query_requirement}'")
        similar_docs = self.retriever.get_similar_requirements(query_requirement, top_k=2)
        
        # 3. Celiski analizi yap (LLM)
        results = []
        for doc in similar_docs:
            print(f"\nAnaliz ediliyor: {doc.page_content[:50]}...")
            analysis = self.detector.analyze_conflict(query_requirement, doc.page_content)
            results.append({
                "source_requirement": query_requirement,
                "compared_with": doc.page_content,
                "analysis": analysis
            })
            
        return results

if __name__ == "__main__":
    workflow = SRSWorkflow()
    
    # Test Senaryosu: Mevcut PDF'i yukle ve yeni bir madde ile celiski ara
    pdf_path = str(Path(__file__).resolve().parent.parent / "ornek_srs.pdf")
    yeni_madde = "Sistem raporlama islemlerini kesinlikle yapmamalidir." # ornek_srs'de REQ-003 ile celisir
    
    final_results = workflow.process_and_analyze(pdf_path, yeni_madde)
    
    print("\n--- FINAL ANALIZ RAPORU ---")
    for item in final_results:
        status = "!!! CELISKI VAR" if item["analysis"]["conflict"] else "OK - Celiski Yok"
        print(f"\nDurum: {status}")
        print(f"Sebep: {item['analysis'].get('reason')}")
        print(f"Ciddiyet: {item['analysis'].get('severity')}")
