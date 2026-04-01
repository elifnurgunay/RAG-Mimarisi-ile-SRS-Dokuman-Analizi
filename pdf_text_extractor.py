import fitz  # PyMuPDF kütüphanesi bu isimle içe aktarılır
import re


def extract_pdf_text(pdf_path: str) -> str:
    """PDF dosyasındaki tüm metni çıkarır ve tek bir string olarak döndürür."""
    text_pages = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text_pages.append(page.get_text("text"))
    return "\n".join(text_pages)


def parse_requirements(text: str) -> list[dict]:
    """Metindeki REQ-xxx başlıklarını tespit eder ve her gereksinimi ayrı bir obje halinde döndürür."""
    pattern = re.compile(r"(REQ-\d{3})")
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    requirements = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        lines = block.splitlines()
        req_id = match.group(1)

        if len(lines) > 1:
            raw_first_line = lines[0]
            rest_of_first_line = raw_first_line[len(req_id):].strip(" :\t")
            content_lines = [rest_of_first_line] + lines[1:]
            content = "\n".join([line for line in content_lines if line.strip()])
        else:
            content = ""

        requirements.append({
            "Requirement_ID": req_id,
            "Content": content
        })

    return requirements


if __name__ == "__main__":
    # Örnek SRS PDF dosyasının adı
    pdf_path = "ornek_srs.pdf"

    # 1. PyMuPDF ile PDF'ten metni çıkar
    string1 = extract_pdf_text(pdf_path)
    print("PDF'ten çıkarılan ham metin (string1):\n")
    print(string1)

    # 2. Regex ile REQ-xxx başlıklarını ayrıştır
    print("\n---\n")
    gereksinimler = parse_requirements(string1)
    print(f"Toplam {len(gereksinimler)} gereksinim bulundu:\n")
    for item in gereksinimler:
        print(f"{item['Requirement_ID']}: {item['Content']}\n")
