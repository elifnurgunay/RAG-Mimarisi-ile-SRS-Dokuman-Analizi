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
        self.retriever = SRSRetriever(collection_name="elif_logic_collection")
        self.analyzer = SRSAnalyzer()
        self.detector = ConflictDetector()

    def run_full_analysis(self, document_chunks):
        analysis_results = []
        
        for chunk in document_chunks:
            # Chunking aşamasında kesinlikle bir req_id üretildiğini bildiğimiz için doğrudan çek
            # Varsayılan olarak güvenlik için AUTO-UNKNOWN ekle
            current_req_id = chunk["metadata"].get("req_id", "AUTO-UNKNOWN-1")
            
            # Analizi çalıştır
            result = self.analyzer.run_analysis(
                chunk_text=chunk["text"], 
                metadata=chunk["metadata"]
            )
            
            # Sonuçları topla
            analysis_results.append({
                "req_id": current_req_id,
                "analysis": result
            })
            
        # Cross-Check (Çapraz Kontrol) aşaması
        # Sistem AUTO-... ile REQ-... ID'lerini mantıksal olarak aynı değerde "benzersiz anahtar"
        # olarak görecek ve filtrelemeyi yapacak.
        cross_check_report = self.detector.evaluate_relationships(analysis_results)
        
        return analysis_results, cross_check_report
