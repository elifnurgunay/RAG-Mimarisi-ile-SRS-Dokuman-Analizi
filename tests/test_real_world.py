import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.interface.workflow import SRSWorkflow
from src.infrastructure.search_optimization import SearchOptimizer

def run_real_world_test():
    print("="*60)
    print("REAL-WORLD CASE STUDY: TELETAS SRS DOKUMANI")
    print("="*60)

    pdf_path = os.path.join("data", "teletas_srs_arastirma.pdf")
    if not os.path.exists(pdf_path):
        print(f"HATA: Dokuman bulunamadi: {pdf_path}")
        return

    # 1. Workflow ve Qdrant baslatimi
    workflow = SRSWorkflow()
    # Gercek test icin temiz bir koleksiyon kullanalim
    workflow.retriever.collection_name = "real_world_teletas_v1"

    # 2. PDF'i Oku, Parcala (Chunking) ve Qdrant'a Yukle
    print(f"[*] PDF isleniyor ve Qdrant'a yukleniyor: {pdf_path}")
    success = workflow.retriever.load_and_index_pdf(pdf_path)
    if not success:
        print("[!] PDF isleme basarisiz oldu.")
        return

    # 3. Yuklenen dokumanlari cek
    all_chunks = workflow.retriever.get_all_documents()
    print(f"[+] Qdrant'tan {len(all_chunks)} chunk (parca/gereksinim) cikarildi.")

    if len(all_chunks) == 0:
        print("[!] PDF'den hicbir chunk cikarilamadi.")
        return

    # 4. Hybrid Search ve LLM ile Celiski Taramasi
    print("\n[*] Hybrid Search ile celiski taramasi basladi...")
    print("[*] (Token limitine takilmamak icin her parcanin en yakin 2 adayi kontrol edilecek)\n")
    
    optimizer = SearchOptimizer()
    all_texts = [chunk.page_content for chunk in all_chunks]
    
    cross_check_results = []
    checked_pairs = set()

    for i, chunk in enumerate(all_chunks):
        req_content = chunk.page_content
        req_id = chunk.metadata.get("req_id", f"PARCA-{i}")

        # Gercek dokumanlarda ayni konudan bahseden cok fazla madde olur.
        # Bu yuzden top_k=2 yaparak sadece en cok benzeyenleri aliyoruz.
        hybrid_results = optimizer.hybrid_search(req_content, all_texts, top_k=2)

        for doc_index, score in hybrid_results:
            cand_chunk = all_chunks[doc_index]
            cand_id = cand_chunk.metadata.get("req_id", f"PARCA-{doc_index}")
            cand_text = cand_chunk.page_content

            if cand_id == req_id or cand_text == req_content:
                continue

            pair_key = tuple(sorted([req_id, cand_id]))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            # LLM Analizi
            try:
                conflict = workflow.detector.analyze_conflict(req_content, cand_text)
                
                # Rate limit kontrolu
                reason_text = conflict.get("reason", "")
                if "rate_limit" in reason_text or "429" in reason_text or "Rate limit" in reason_text:
                    print(f"  [LIMIT] API limiti, 5sn bekleniyor...")
                    time.sleep(5)
                    conflict = workflow.detector.analyze_conflict(req_content, cand_text)
                
                time.sleep(1.5)  # API kotasi icin bekleme
                
                if conflict.get("conflict"):
                    cross_check_results.append({
                        "req1": req_id,
                        "req2": cand_id,
                        "reason": conflict.get("reason", ""),
                        "severity": conflict.get("severity", "")
                    })
                    print(f"  [!] CELISKI BULUNDU: {req_id} <--> {cand_id} ({conflict.get('severity')})")
                else:
                    # Ekrani cok kirletmemek icin sadece nokta basiyoruz
                    print(".", end="", flush=True)

            except Exception as e:
                print(f"\n  [HATA] {req_id}: {e}")
                time.sleep(2)

    print("\n\n" + "="*50)
    print("REAL-WORLD TEST SONUCLARI")
    print("="*50)
    print(f"Taranan Toplam Parca : {len(all_chunks)}")
    print(f"Kontrol Edilen Cift  : {len(checked_pairs)}")
    print(f"Bulunan Celiski      : {len(cross_check_results)}")
    
    if cross_check_results:
        print("\n--- DETAYLI CELISKI RAPORU ---")
        for i, c in enumerate(cross_check_results):
            print(f"\n{i+1}. {c['req1']} <--> {c['req2']} | Uyari Seviyesi: {c['severity']}")
            print(f"   Analiz: {c['reason']}")
    else:
        print("\nDokumanda hicbir celiski bulunamadi. Mukemmel yazilmis bir SRS olabilir veya RAG parcalari yeterince ortusmemis olabilir.")

if __name__ == "__main__":
    run_real_world_test()
