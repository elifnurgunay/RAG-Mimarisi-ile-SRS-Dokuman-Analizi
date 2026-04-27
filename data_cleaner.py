import json
import sys
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pdf_text_extractor import extract_pdf_text, parse_requirements


def clean_and_save_requirements(pdf_path: str, output_path: str = "cleaned_requirements.json"):
    """
    PDF dosyasından gereksinimleri çıkarır, temizler ve JSON formatına dönüştürür.
    
    Args:
        pdf_path (str): PDF dosyasının yolu
        output_path (str): Çıktı JSON dosyasının adı (varsayılan: cleaned_requirements.json)
    """
    try:
        # PDF'den metni çıkar
        text = extract_pdf_text(pdf_path)
        if not text or not text.strip():
            print(f"Hata: {pdf_path} dosyasından metin çıkarılamadı.")
            return
        
        # Gereksinimleri parse et
        requirements = parse_requirements(text)
        if not requirements:
            print("Uyarı: PDF içinde REQ-xxx biçiminde hiçbir gereksinim bulunamadı.")
            return
        
        # Temizlenmiş formatta dönüştür
        cleaned_requirements = []
        for req in requirements:
            cleaned_requirements.append({
                "id": req["Requirement_ID"],
                "text": req["Content"].strip()
            })
        
        # UTF-8 ile JSON dosyasına kaydet
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_requirements, f, ensure_ascii=False, indent=4)
        
        print(f"✅ Temizlenmiş gereksinimler başarıyla '{output_path}' dosyasına kaydedildi.")
        print(f"   Toplam {len(cleaned_requirements)} gereksinim işlendi.")
        
    except FileNotFoundError:
        print(f"Hata: '{pdf_path}' dosyası bulunamadı.")
    except Exception as e:
        print(f"Hata: Gereksinim temizleme işlemi sırasında bir sorun oluştu: {e}")


if __name__ == "__main__":
    # Varsayılan PDF dosyası ile çalıştır
    pdf_file = "ornek_srs.pdf"
    clean_and_save_requirements(pdf_file)