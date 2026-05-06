import os
import sys
from pathlib import Path

# Yol ayarı
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.retriever import SRSRetriever
from src.core.analyzer import SRSAnalyzer, calculate_score
from src.core.logic import ConflictDetector

class SRSWorkflow:
    def __init__(self):
        self.retriever = SRSRetriever(collection_name="elif_logic_collection")
        self.analyzer = SRSAnalyzer()
        self.detector = ConflictDetector()

    def run_full_analysis(self, pdf_path: str):
        print(f"--- İş akışı başladı: {pdf_path} ---")
        
        # 1. PDF İndeksleme
        if not self.retriever.load_and_index_pdf(pdf_path):
            print("HATA: PDF okunamadı.")
            return None

        # 2. Veritabanından tüm metni çek (Analiz için)
        all_chunks = self.retriever.get_all_documents()
        
        if not all_chunks:
            print("HATA: Veritabanından veri çekilemedi.")
            return None
            
        # Chunkları sayfa/index sırasına göre dizmek iyi olabilir (metadata varsa)
        try:
            all_chunks.sort(key=lambda x: x.metadata.get('chunk_index', 0))
        except:
            pass

        full_text = "\n".join([doc.page_content for doc in all_chunks])

        # 3. Analiz Motorunu Çalıştır
        print("LLM Analiz motoru çalışıyor...")
        report = self.analyzer.analyze_text(full_text, doc_name=os.path.basename(pdf_path))
        
        if not report:
            print("HATA: Rapor oluşturulamadı.")
            return None

        # 4. Çapraz Çelişki Kontrolü (RAG) - Toplu İşleme ile Optimize Edildi
        cross_check_results = []
        processed_pairs = set() # Aynı çiftleri tekrar kontrol etmemek için
        
        # Sadece REQ içeren chunkları filtrele
        req_chunks = [c for c in all_chunks if "REQ-" in c.page_content]
        
        print(f"Toplam {len(req_chunks)} gereksinim maddesi için çapraz kontrol yapılıyor...")
        
        for i, chunk in enumerate(req_chunks):
            req_content = chunk.page_content
            req_id = chunk.metadata.get("req_id", f"ID-{i}")
            
            # Bu madde ile en benzer 3 maddeyi getir
            similar_docs = self.retriever.get_similar_requirements(req_content, top_k=3)
            
            # Adayları topla (kendisi hariç)
            candidates = []
            for doc in similar_docs:
                if doc.page_content != req_content:
                    candidates.append(doc.page_content)
            
            if candidates:
                # Toplu çelişki kontrolü (Tek API çağrısı)
                conflicts = self.detector.batch_conflict_check(req_content, candidates)
                
                for conflict in conflicts:
                    # Raporlanacak formatta hazırla
                    cross_check_results.append({
                        "req_id": req_id,
                        "conflict_with_text": conflict.get("conflict_with_text", ""),
                        "reason": conflict.get("reason", "Çelişki tespit edildi."),
                        "severity": conflict.get("severity", "Medium")
                    })
            
            # Her 5 maddede bir kısa bekleme (API sağlığı için)
            if i % 5 == 0:
                import time
                time.sleep(1)
        
        return {
            "report": report,
            "cross_checks": cross_check_results
        }
