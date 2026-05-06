import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.interface.workflow import SRSWorkflow
from src.infrastructure.search_optimization import SearchOptimizer

def run_stress_test():
    print("="*60)
    print("SRS HYBRID SEARCH STRES TESTI (Qdrant + BM25 + Vektor)")
    print("="*60)

    # 1. Workflow başlat - Qdrant bağlantısı burada kurulur
    workflow = SRSWorkflow()
    workflow.retriever.collection_name = "test_stress_final_v6"

    # 2. Test Verisini Yükle (temiz, notasyonsuz)
    test_file = "../stres_testi_srs.txt"
    with open(test_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.startswith("REQ-")]

    structured_data = []
    for line in lines:
        parts = line.split(":", 1)
        if len(parts) == 2:
            structured_data.append({"id": parts[0].strip(), "text": parts[1].strip()})

    print(f"[*] {len(structured_data)} madde Qdrant'a yukleniyor...")
    # Qdrant'a batch olarak yükle (mimari ayakta kalıyor)
    workflow.retriever.add_structured_data(structured_data)
    print("[+] Yukleme tamamlandi.")

    # 3. Qdrant'tan TÜM dokümanları çek
    print("[*] Qdrant'tan tum dokumanlar cekiliyor...")
    all_chunks = workflow.retriever.get_all_documents()
    print(f"[+] {len(all_chunks)} chunk Qdrant'tan alindi.")

    # 4. SearchOptimizer ile lokal Hybrid Search reranking
    #    Qdrant veri saklıyor, SearchOptimizer sıralıyor - ikisi birlikte çalışıyor
    optimizer = SearchOptimizer()
    all_texts = [chunk.page_content for chunk in all_chunks]
    all_ids   = [chunk.metadata.get("req_id", f"IDX-{i}") for i, chunk in enumerate(all_chunks)]

    # Ground Truth
    expected_conflict_pairs = [
        ("REQ-001", "REQ-010"),
        ("REQ-005", "REQ-012"),
        ("REQ-004", "REQ-013"),
        ("REQ-015", "REQ-016"),
        ("REQ-017", "REQ-018"),
        ("REQ-006", "REQ-019"),
        ("REQ-014", "REQ-020"),
    ]
    total_expected = len(expected_conflict_pairs)

    print(f"\n[*] Hybrid Search ile celiski taramasi basladi ({len(all_chunks)} madde)...\n")
    cross_check_results = []
    checked_pairs = set()

    for i, chunk in enumerate(all_chunks):
        req_content = chunk.page_content
        req_id = chunk.metadata.get("req_id", f"IDX-{i}")

        # Hybrid Search: BM25 + Dense vektör ile en yakın top_k adayı bul
        hybrid_results = optimizer.hybrid_search(req_content, all_texts, top_k=3)

        for doc_index, score in hybrid_results:
            cand_chunk = all_chunks[doc_index]
            cand_id    = cand_chunk.metadata.get("req_id", f"IDX-{doc_index}")
            cand_text  = cand_chunk.page_content

            if cand_id == req_id:
                continue

            pair_key = tuple(sorted([req_id, cand_id]))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            # LLM ile çelişki analizi (ConflictDetector Qdrant mimarisinin parçası)
            try:
                conflict = workflow.detector.analyze_conflict(req_content, cand_text)
                
                # Rate limit hatası sessizce "conflict: False" dönüyor mu kontrol et
                reason_text = conflict.get("reason", "")
                if "rate_limit" in reason_text or "429" in reason_text or "Rate limit" in reason_text:
                    print(f"  [LIMIT]   {pair_key[0]} -- {pair_key[1]} (API limiti, 5sn bekleniyor...)")
                    time.sleep(5)
                    # Tekrar dene
                    conflict = workflow.detector.analyze_conflict(req_content, cand_text)
                    reason_text = conflict.get("reason", "")
                    if "rate_limit" in reason_text or "429" in reason_text or "Rate limit" in reason_text:
                        print(f"  [SKIP]    {pair_key[0]} -- {pair_key[1]} (Hala limit, atlaniyor)")
                        continue
                
                time.sleep(1.5)  # Groq RPM koruma (daha uzun bekleme)
                if conflict.get("conflict"):
                    cross_check_results.append({
                        "pair": pair_key,
                        "reason": conflict.get("reason", ""),
                        "severity": conflict.get("severity", "")
                    })
                    print(f"  [CELISKI] {pair_key[0]} <--> {pair_key[1]} | {conflict.get('severity','?')}")
                else:
                    print(f"  [ temiz ] {pair_key[0]} -- {pair_key[1]}")
            except Exception as e:
                print(f"  [HATA]    {req_id} / {cand_id}: {e}")
                time.sleep(3)
                continue

    # 5. Performans Metrikleri
    found_pairs = [c["pair"] for c in cross_check_results]
    true_positives = sum(
        1 for exp in expected_conflict_pairs
        if tuple(sorted(exp)) in found_pairs
    )

    total_found = len(found_pairs)
    precision = true_positives / total_found    if total_found    > 0 else 0
    recall    = true_positives / total_expected if total_expected > 0 else 0
    f1        = 2*(precision*recall)/(precision+recall) if (precision+recall) > 0 else 0

    print("\n" + "="*55)
    print("PERFORMANS METRIKLERI  [Qdrant + BM25 + Vektor Hybrid]")
    print("="*55)
    print(f"Beklenen Celiski Cifti  : {total_expected}")
    print(f"Toplam Kontrol Edilen   : {len(checked_pairs)} cift")
    print(f"AI'nin Buldugu Celiski  : {total_found}")
    print(f"Dogru Tespit (TP)       : {true_positives}")
    print("-"*30)
    print(f"Precision (Kesinlik)   : {precision:.2%}")
    print(f"Recall (Duyarlilik)    : {recall:.2%}")
    print(f"F1-Score (Genel)       : {f1:.2%}")
    print("="*55)

    if f1 >= 0.8:
        print("SONUC: Mukemmel! Hybrid Search celiski tespitini iyilestirdi.")
    elif f1 >= 0.5:
        print("SONUC: Iyi performans. Bazi kenar vakalar kacirildi.")
    else:
        print("SONUC: Dusuk recall. top_k veya embedding modeli gozden gecirilmeli.")

    if cross_check_results:
        print("\n--- BULUNAN CELISKILER ---")
        for i, c in enumerate(cross_check_results):
            expected_mark = "[BEKLENEN]" if c["pair"] in [tuple(sorted(p)) for p in expected_conflict_pairs] else "[FAZLADAN]"
            print(f"{i+1}. {expected_mark} {c['pair'][0]} <--> {c['pair'][1]} ({c['severity']})")
            print(f"   {c['reason'][:110]}...")

if __name__ == "__main__":
    run_stress_test()
