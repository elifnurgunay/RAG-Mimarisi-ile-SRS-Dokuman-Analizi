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

        # 4. Çapraz Çelişki Kontrolü (RAG) - Daha kapsamlı hale getirildi
        cross_check_results = []
        # Her bulunan hata için değil, her gereksinim için potansiyel çelişki ara
        for chunk in all_chunks:
            req_content = chunk.page_content
            req_id = chunk.metadata.get("req_id", "ID-YOK")
            
            # Sadece REQ içeren chunklar için arama yap (performans için)
            if "REQ-" in req_content:
                # Bu madde ile çelişebilecek maddeleri ara
                # (Kendi hariç en yakınları getir)
                similar_docs = self.retriever.get_similar_requirements(req_content, top_k=3)
                
                for doc in similar_docs:
                    # Kendisiyle karşılaştırma yapma
                    if doc.page_content == req_content:
                        continue
                        
                    conflict = self.detector.analyze_conflict(req_content, doc.page_content)
                    if conflict.get("conflict"):
                        # Eğer bu çelişki zaten raporlanmadıysa ekle
                        is_already_added = any(c["req_id"] == req_id and c["conflict_with_text"][:50] == doc.page_content[:50] for c in cross_check_results)
                        if not is_already_added:
                            cross_check_results.append({
                                "req_id": req_id,
                                "conflict_with_text": doc.page_content[:150],
                                "reason": conflict.get("reason"),
                                "severity": conflict.get("severity")
                            })
        
        return {
            "report": report,
            "cross_checks": cross_check_results
        }
