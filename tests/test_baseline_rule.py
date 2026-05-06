import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def run_baseline_rule():
    print("="*60)
    print("BASELINE DENEY 3: KURAL TABANLI (YAPAY ZEKA YOK)")
    print("="*60)

    # 1. Veriyi Oku
    test_file = "stres_testi_srs.txt"
    with open(test_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.startswith("REQ-")]

    structured_data = []
    for line in lines:
        parts = line.split(":", 1)
        if len(parts) == 2:
            structured_data.append({"id": parts[0].strip(), "text": parts[1].strip()})

    print(f"[*] {len(structured_data)} madde basit kural setiyle taranacak...")

    # 2. Kurallar (Antonyms / Mutually Exclusive keywords)
    # Eger iki kelimeden biri bir cümlede, digeri baska cümlede varsa çeliski say
    conflict_rules = [
        ("iOS", "Android"),
        ("mavi", "kirmizi"),
        ("sifrelenmeli", "sifrelenmemeli"),
        ("Excel", "PDF"),
        ("kapali ag", "internet erisimine acik"),
        ("30 gun", "1 hafta"),
        ("10 kullanici", "1000 kullanici")
    ]

    # Ground Truth
    expected_conflict_pairs = [
        ("REQ-001", "REQ-010"), ("REQ-005", "REQ-012"), ("REQ-004", "REQ-013"),
        ("REQ-015", "REQ-016"), ("REQ-017", "REQ-018"), ("REQ-006", "REQ-019"),
        ("REQ-014", "REQ-020")
    ]
    total_expected = len(expected_conflict_pairs)

    found_conflicts = []
    
    # 3. Kural Motoru Çalistirma (O(n^2))
    for i in range(len(structured_data)):
        for j in range(i + 1, len(structured_data)):
            req1 = structured_data[i]
            req2 = structured_data[j]
            
            text1 = req1["text"].lower()
            text2 = req2["text"].lower()

            # Her kural cifti icin kontrol et
            for word1, word2 in conflict_rules:
                word1 = word1.lower()
                word2 = word2.lower()
                
                # word1 text1'de ve word2 text2'de
                if (word1 in text1 and word2 in text2) or (word2 in text1 and word1 in text2):
                    pair = tuple(sorted([req1["id"], req2["id"]]))
                    if pair not in found_conflicts:
                        found_conflicts.append(pair)

    # 4. Performans Hesaplama
    true_positives = 0
    for exp_pair in expected_conflict_pairs:
        if tuple(sorted(exp_pair)) in found_conflicts:
            true_positives += 1

    total_found = len(found_conflicts)
    precision = true_positives / total_found if total_found > 0 else 0
    recall = true_positives / total_expected if total_expected > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print("\n" + "="*50)
    print("PERFORMANS METRIKLERI [Rule-Based / Kural Tabanli]")
    print("="*50)
    print(f"Beklenen Celiski Cifti  : {total_expected}")
    print(f"Sistemin Buldugu Toplam : {total_found}")
    print(f"Dogru Tespit (TP)       : {true_positives}")
    print("-" * 30)
    print(f"Precision (Kesinlik)   : {precision:.2%}")
    print(f"Recall (Duyarlilik)    : {recall:.2%}")
    print(f"F1-Score (Genel)       : {f1:.2%}")
    print("="*50)
    
    if found_conflicts:
        print("\n--- Kurallarin Buldugu Bazi Celiskiler ---")
        for i, c in enumerate(found_conflicts[:5]):
            print(f"{i+1}. {c[0]} <--> {c[1]}")

if __name__ == "__main__":
    run_baseline_rule()
