import fitz  # PyMuPDF kütüphanesi bu isimle içe aktarılır
import re

class SRSParser:
    def __init__(self, file_path):
        self.file_path = file_path
        # REQ-001, REQ-012 gibi yapıları yakalayacak Regex deseni
        # Eğer format REQ-1 ise regex'i r"(REQ-\d+)" olarak değiştirebilirsin
        self.req_pattern = re.compile(r"(REQ-\d{3})")

    def extract_text(self):
        """PDF dosyasından tüm metni çıkarıp tek bir string olarak döner."""
        try:
            pages_text = []
            with fitz.open(self.file_path) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    pages_text.append(page.get_text("text"))
            return "\n".join(pages_text)
        except Exception as e:
            print(f"PDF metin çıkarılırken bir hata oluştu: {e}")
            return None

    def extract_text_and_parse(self):
        extracted_data = []

        try:
            # PDF dosyasını aç
            with fitz.open(self.file_path) as doc:
                # Sayfalar üzerinde gezin
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    # Sayfadaki metni düz metin (text) formatında çek
                    text = page.get_text("text")

                    # Çekilen metin içinde Regex ile eşleşmeleri bul
                    matches = self.req_pattern.finditer(text)

                    for match in matches:
                        req_id = match.group(1)
                        # Bulunan gereksinimi ve bulunduğu sayfayı listeye ekle
                        extracted_data.append({
                            "Requirement_ID": req_id,
                            "Page": page_num + 1
                        })

            return extracted_data

        except Exception as e:
            print(f"PDF okunurken bir hata oluştu: {e}")
            return None


# --- Kodu Test Etme ---
if __name__ == "__main__":
    # Test etmek için aynı klasöre 'ornek_srs.pdf' adında bir dosya koymalısın
    pdf_yolu = "ornek_srs.pdf"

    parser = SRSParser(pdf_yolu)

    # Önce ham metni çıkar ve ekranda göster
    ham_metin = parser.extract_text()
    if ham_metin is not None:
        print("PDF'ten çıkan ham metin:\n")
        print(ham_metin)
        print("\n---\n")

    # Ardından REQ-xxx başlıklarını ayrıştır
    sonuclar = parser.extract_text_and_parse()
    if sonuclar:
        print(f"Toplam {len(sonuclar)} adet gereksinim bulundu:\n")
        for item in sonuclar:
            print(f"Bulunan: {item['Requirement_ID']} (Sayfa: {item['Page']})")
