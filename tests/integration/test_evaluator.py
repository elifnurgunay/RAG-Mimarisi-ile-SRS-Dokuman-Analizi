import sys
import os
from typing import List
import pytest

# Proje kök dizinini Python yoluna ekle (Import hatalarını önlemek için)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.core.analyzer import SRSAnalyzer
except ImportError as e:
    pytest.fail(f"Import failed: {e}")

def calculate_metrics(true_positives, total_ai_found, total_actual_issues):
    """Precision, Recall ve F1-Score hesaplar."""
    precision = true_positives / total_ai_found if total_ai_found > 0 else 0
    recall = true_positives / total_actual_issues if total_actual_issues > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    return precision, recall, f1

def run_performance_test():
    print("="*50)
    print("SRS ANALIZ MOTORU PERFORMANS TESTI BASLADI")
    print("="*50)

    # 1. Analizciyi Başlat
    try:
        analyzer = SRSAnalyzer()
    except Exception as e:
        print(f"Hata: Analiz motoru başlatılamadı: {e}")
        return

    # 2. Test Senaryosu (Ground Truth)
    # ornek_srs.pdf içindeki 3 madde de ISO/IEC/IEEE 29148'e göre 'Incomplete' veya 'Ambiguous' kabul edilir.
    test_text = """
    REQ-001: Sistem login islemleri
    REQ-002: Kullanici kayit formu
    REQ-003: Raporlama modulunun calismasi
    """
    
    expected_ids = ["REQ-001", "REQ-002", "REQ-003"]
    total_actual_issues = len(expected_ids)

    print(f"[*] Test edilecek gereksinim sayisi: {total_actual_issues}")
    print("[*] LLM Analizi yapiliyor, lutfen bekleyin...\n")

    # 3. Analizi Çalıştır
    try:
        report = analyzer.analyze_text(test_text, "Test_Evaluation_Report")
    except Exception as e:
        print(f"Hata: Analiz sirasinda bir sorun olustu: {e}")
        return

    # 4. Sonuçları Değerlendir
    ai_found_issues = report.issues
    total_ai_found = len(ai_found_issues)
    
    # Hangi gerçek hatalar bulundu? (True Positives)
    # AI'nın bulduğu her hata, bizim beklediğimiz bir ID'ye aitse TP sayılır.
    found_ids = [issue.req_id.upper() for issue in ai_found_issues]
    true_positives = len(set(found_ids) & set(expected_ids))

    # 5. Metrikleri Hesapla
    precision, recall, f1 = calculate_metrics(true_positives, total_ai_found, total_actual_issues)

    # 6. Raporu Yazdır
    print("-" * 30)
    print(f"ANALIZ OZETI")
    print("-" * 30)
    for issue in ai_found_issues:
        print(f"OK [{issue.req_id}] {issue.type} - {issue.severity}: {issue.problem[:60]}...")

    print("\n" + "="*50)
    print("PERFORMANS METRIKLERI")
    print("="*50)
    print(f"Beklenen Hata Sayisi   : {total_actual_issues}")
    print(f"AI'nin Tespit Ettigi   : {total_ai_found}")
    print(f"Dogru Tespit (TP)     : {true_positives}")
    print("-" * 30)
    print(f"Precision (Kesinlik)  : {precision:.2%}")
    print(f"Recall (Duyarlilik)   : {recall:.2%}")
    print(f"F1-Score (Genel)      : {f1:.2%}")
    print("="*50)
    
    if f1 > 0.8:
        print("SONUC: Sistem yuksek dogrulukla calisiyor!")
    elif f1 > 0.5:
        print("SONUC: Sistem orta seviye performans gosteriyor, prompt iyilestirilebilir.")
    else:
        print("SONUC: Performans dusuk. Gereksinim parcalama veya prompt kontrol edilmeli.")

if __name__ == "__main__":
    run_performance_test()
