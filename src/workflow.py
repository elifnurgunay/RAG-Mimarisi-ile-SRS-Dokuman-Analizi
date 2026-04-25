import os
import sys
from pathlib import Path

# Yol ayarı
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.retriever import SRSRetriever
from src.analyzer import SRSAnalyzer, calculate_score
from src.logic import ConflictDetector

class SRSWorkflow:
    def __init__(self):
        # Koleksiyon adının retriever.py ile aynı olduğundan emin ol (Örn: elif_logic_collection)
        self.retriever = SRSRetriever(collection_name="elif_logic_collection")
        self.analyzer = SRSAnalyzer()
        self.detector = ConflictDetector()

    def run_full_analysis(self, pdf_path: str):
        print(f"--- İş akışı başladı: {pdf_path} ---")
        
        # 1. PDF'i İndeksle
        if not self.retriever.load_and_index_pdf(pdf_path):
            print("HATA: PDF okunamadı.")
            return None

        # 2. Veritabanından tüm metni çek (Analiz için)
        # Not: Boş sorgu ("") bazen boş dönebilir, o yüzden genel bir terimle aratalım
        all_chunks = self.retriever.get_similar_requirements("gereksinim", top_k=20)
        
        if not all_chunks:
            print("HATA: Veritabanından veri çekilemedi.")
            return None
            
        full_text = "\n".join([doc.page_content for doc in all_chunks])

        # 3. Analiz Motorunu Çalıştır
        print("LLM Analiz motoru çalışıyor...")
        report = self.analyzer.analyze_text(full_text, doc_name=os.path.basename(pdf_path))
        
        if not report:
            print("HATA: Rapor oluşturulamadı.")
            return None

        # 4. Çapraz Çelişki Kontrolü (RAG)
        cross_check_results = []
        for issue in report.issues:
            if issue.type == "Inconsistency":
                # Bu hata ile ilgili benzer maddeleri bul
                similar_docs = self.retriever.get_similar_requirements(issue.problem, top_k=2)
                for doc in similar_docs:
                    conflict = self.detector.analyze_conflict(issue.problem, doc.page_content)
                    if conflict.get("conflict"):
                        cross_check_results.append({
                            "req_id": issue.req_id,
                            "conflict_with_text": doc.page_content[:150],
                            "reason": conflict.get("reason"),
                            "severity": conflict.get("severity")
                        })
        
        return {
            "report": report,
            "cross_checks": cross_check_results
        }