"""
src/utils/text_utils.py

Metin ön-işleme ve biçimlendirme için yardımcı fonksiyonlar.
"""
import re
from typing import List


def normalize_whitespace(text: str) -> str:
    """
    Birden fazla boşluğu / satır sonunu tek boşluğa indirger,
    baştaki ve sondaki boşlukları temizler.
    """
    return re.sub(r"\s+", " ", text).strip()


def truncate_text(text: str, max_chars: int = 200, suffix: str = "...") -> str:
    """
    Metni `max_chars` karakterle sınırlar; uzunsa `suffix` ekler.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + suffix


def split_into_batches(lines: List[str], max_chars: int = 5000) -> List[str]:
    """
    Satır listesini maksimum `max_chars` karakter uzunluğundaki
    batch'lere (string) böler. Büyük metinlerin LLM'e gönderilmesi için kullanılır.

    Args:
        lines:     Metin satırlarının listesi.
        max_chars: Her batch'in maksimum karakter sayısı.

    Returns:
        Her elemanı bir batch string olan liste.
    """
    batches: List[str] = []
    current: List[str] = []
    current_len = 0

    for line in lines:
        if current_len + len(line) > max_chars and current:
            batches.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)

    if current:
        batches.append("\n".join(current))

    return batches


def extract_req_ids(text: str) -> List[str]:
    """
    Metindeki REQ-xxx tarzı gereksinim ID'lerini çıkarır.

    Desteklenen formatlar: REQ-001, REQ001, R-1, R.1, GEREKSINIM-3
    """
    pattern = r"\b(?:REQ|GEREKSINIM|R)[-.\s]?\d+\b"
    return re.findall(pattern, text, flags=re.IGNORECASE)


def is_noise_line(line: str) -> bool:
    """
    Bir satırın analiz için gürültü (Şekil, Tablo, Sayfa No vb.) olup olmadığını belirler.
    """
    line = line.strip()
    if not line:
        return True
    
    # 1. Sayfa numaraları (örn: "Sayfa 1 / 5", "12")
    if re.match(r"^(Sayfa\s*\d+|\d+)$", line, re.IGNORECASE):
        return True
    
    # 2. Şekil ve Tablo etiketleri (örn: "Şekil 5: Diyagram", "Tablo 1.1")
    # Eğer satır çok kısaysa ve bu kelimelerle başlıyorsa gürültüdür.
    if len(line) < 100:
        noise_patterns = [
            r"^(Şekil|Sekil|Figure|Fig\.|Tablo|Table|Görsel|Resim)\s*[-.:]?\s*\d+",
            r"^(Kaynak|Referans|Bölüm|Kısım)\s*[-.:]?\s*\d+",
        ]
        for p in noise_patterns:
            if re.match(p, line, re.IGNORECASE):
                return True
                
    return False


def clean_noise(text: str) -> str:
    """
    Metindeki gürültülü satırları ayıklayarak temiz bir metin döndürür.
    """
    lines = text.split("\n")
    cleaned = [line for line in lines if not is_noise_line(line)]
    return "\n".join(cleaned)
