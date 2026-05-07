import json
import sys
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.parsing.pdf_parser import PDFParser


def clean_and_save_requirements(pdf_path: str, output_path: str = "cleaned_requirements.json"):
    """
    PDF dosyasından gereksinimleri çıkarır, temizler ve JSON formatına dönüştürür.
    
    Args:
        pdf_path (str): PDF dosyasının yolu
        output_path (str): Çıktı JSON dosyasının adı (varsayılan: cleaned_requirements.json)
    """
    try:
        # PDFParser başlat
        parser = PDFParser(pdf_path)
        
        # PDF'i parse et
        parsed_data = parser.parse_pdf()
        requirements = parsed_data.get("requirements", [])
        
        if not requirements:
            print("Uyarı: PDF içinde REQ-xxx biçiminde hiçbir gereksinim bulunamadı.")
            return
        
        # Temizlenmiş formatta dönüştür
        cleaned_requirements = []

        for req in requirements:
            cleaned_requirements.append({
            "id": req["Requirement_ID"],
            "text": req.get("text", "").strip()
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
