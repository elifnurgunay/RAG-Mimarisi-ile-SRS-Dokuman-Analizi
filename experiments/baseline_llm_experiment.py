import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.config import GROQ_API_KEY



def run_baseline_llm():
    print("="*60)
    print("BASELINE DENEY 2: SADECE LLM (RAG YOK)")
    print("="*60)

    # 1. Veriyi Oku
    test_file = "../stres_testi_srs.txt"
    with open(test_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.startswith("REQ-")]

    full_document = "\n".join(lines)
    print(f"[*] Tum dokuman tek parca halinde hazirlandi ({len(lines)} madde).")

    # 2. LLM Ayarları (merkezi config üzerinden)
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        groq_api_key=GROQ_API_KEY
    )
    parser = JsonOutputParser()

    prompt_template = """
Sen uzman bir Yazılım Gereksinim Analistisin. 
Aşağıda, bir yazılım projesine ait tüm gereksinimlerin listesi tek parça halinde verilmiştir.
Görev: Bu metnin tamamını oku ve birbiriyle çelişen tüm gereksinim çiftlerini bul.

**Gereksinim Metni:**
{document}

**Analiz Rehberi - Aşağıdakilerden BİRİ bile varsa çelişkidir:**
- Nicel Çelişkiler: (Örn: "max 10 kullanıcı" vs "en az 1000 kullanıcı", "30 gün" vs "1 hafta")
- Mantıksal/Platform Çelişkiler: (Örn: "sadece iOS" vs "sadece Android")
- Tasarım Çelişkileri: (Örn: "mavi tema" vs "kırmızı tema")

Yanıtını SADECE aşağıdaki JSON array formatında ver. Başka hiçbir açıklama yazma.
[
    {{
        "req1_id": "REQ-XXX",
        "req2_id": "REQ-YYY",
        "reason": "neden celisiyorlar"
    }}
]
Eğer hiç çelişki bulamazsan boş liste [] döndür.
"""
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm | parser

    print("[*] Koca dokuman tek seferde LLM'e gonderiliyor (RAG olmadan)...")
    
    start_time = time.time()
    try:
        found_conflicts = chain.invoke({"document": full_document})
    except Exception as e:
        print(f"[!] LLM Hatasi: {e}")
        found_conflicts = []
    
    elapsed = time.time() - start_time
    print(f"[+] LLM Yanit Sureci: {elapsed:.2f} saniye")

    # 3. Ground Truth (Beklenenler)
    expected_conflict_pairs = [
        ("REQ-001", "REQ-010"), ("REQ-005", "REQ-012"), ("REQ-004", "REQ-013"),
        ("REQ-015", "REQ-016"), ("REQ-017", "REQ-018"), ("REQ-006", "REQ-019"),
        ("REQ-014", "REQ-020")
    ]
    total_expected = len(expected_conflict_pairs)

    # 4. Performans Hesaplama
    parsed_found_pairs = []
    for c in found_conflicts:
        r1, r2 = c.get("req1_id"), c.get("req2_id")
        if r1 and r2:
            parsed_found_pairs.append(tuple(sorted([r1, r2])))

    true_positives = 0
    for exp_pair in expected_conflict_pairs:
        if tuple(sorted(exp_pair)) in parsed_found_pairs:
            true_positives += 1

    total_found = len(parsed_found_pairs)
    precision = true_positives / total_found if total_found > 0 else 0
    recall = true_positives / total_expected if total_expected > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print("\n" + "="*50)
    print("PERFORMANS METRIKLERI [Sadece LLM - RAG Yok]")
    print("="*50)
    print(f"Beklenen Celiski Cifti  : {total_expected}")
    print(f"AI'nin Buldugu Toplam   : {total_found}")
    print(f"Dogru Tespit (TP)       : {true_positives}")
    print("-" * 30)
    print(f"Precision (Kesinlik)   : {precision:.2%}")
    print(f"Recall (Duyarlilik)    : {recall:.2%}")
    print(f"F1-Score (Genel)       : {f1:.2%}")
    print("="*50)
    
    if found_conflicts:
        print("\n--- LLM'in Buldugu Bazi Celiskiler ---")
        for i, c in enumerate(found_conflicts[:5]):
            print(f"{i+1}. {c.get('req1_id')} <--> {c.get('req2_id')}: {c.get('reason')}")

if __name__ == "__main__":
    run_baseline_llm()
