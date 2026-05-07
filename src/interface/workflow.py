import os
import sys
from pathlib import Path

# Yol ayarı
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.retriever import SRSRetriever
from src.core.analyzer import SRSAnalyzer
from src.core.conflict_detector import ConflictDetector

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

        # 3. Metni Temizle ve Analiz Motorunu Çalıştır
        from src.utils.text_utils import clean_noise
        cleaned_text = clean_noise(full_text)
        
        print("LLM Analiz motoru çalışıyor...")
        report = self.analyzer.analyze_text(cleaned_text, doc_name=os.path.basename(pdf_path))
        
        if not report:
            print("HATA: Rapor oluşturulamadı.")
            return None

        # 4. Çapraz Çelişki Kontrolü (Global & Hızlı)
        # Her madde için ayrı API çağrısı yapmak yerine toplu analiz yapıyoruz.
        print("Çelişki analizi yapılıyor (Toplu Mod)...")
        
        # Sadece REQ içeren metinleri ve ID'lerini topla
        req_texts = [c.page_content for c in all_chunks if "REQ-" in c.page_content]
        req_ids = [c.metadata.get("req_id", "UNK") for c in all_chunks if "REQ-" in c.page_content]
        
        # Eğer REQ-ID bazlı metin bulunamadıysa tüm metni kullan (ama sınırlı tut)
        if not req_texts:
            req_texts = [c.page_content for c in all_chunks[:20]]
            req_ids = [f"ID-{i}" for i in range(len(req_texts))]

        # Toplu Global Analiz (Döngü yok, tek/az çağrı)
        conflict_objects = self.detector.analyze_global_conflicts(
            requirements=req_texts,
            source_req_ids=req_ids,
            top_k_candidates=2 # Hız için aday sayısını düşürdük
        )
        
        # 5. Final Raporu İnşa Et
        from src.core.report_builder import ReportBuilder
        final_report = ReportBuilder().build(report, conflict_objects)
        
        return final_report
