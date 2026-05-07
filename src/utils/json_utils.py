"""
src/utils/json_utils.py

LLM JSON çıktısını güvenli biçimde parse etmek için yardımcı fonksiyonlar.
LLM bazen JSON bloğunu markdown code fence veya ekstra metin ile döndürür;
bu modül o durumları yakalar ve kurtarır.
"""
import json
import re
from typing import Any, Optional


def extract_json_from_text(text: str) -> str:
    """
    Metinden ilk geçerli JSON bloğunu çıkarır.
    Markdown ```json ... ``` sarmalayıcısını ve çevreleyen metni temizler.

    Returns:
        Düzeltilmiş JSON string.

    Raises:
        ValueError: Hiçbir JSON bloğu bulunamazsa.
    """
    # 1. Markdown code fence varsa temizle
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text)
    if fence_match:
        return fence_match.group(1).strip()

    # 2. Düz JSON objesi veya dizisi bul
    obj_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if obj_match:
        return obj_match.group(1).strip()

    raise ValueError(
        f"Metin içinde geçerli bir JSON bloğu bulunamadı.\n"
        f"Ham çıktı (ilk 300 karakter): {text[:300]}"
    )


def safe_parse_json(text: str, fallback: Optional[Any] = None) -> Any:
    """
    LLM çıktısını JSON olarak parse eder.
    Başarısız olursa `fallback` değerini döndürür (varsayılan: None).

    Args:
        text:     LLM'den gelen ham metin.
        fallback: Parse başarısız olursa döndürülecek değer.

    Returns:
        Parse edilmiş Python nesnesi veya fallback.
    """
    if not text or not text.strip():
        return fallback

    # Önce direkt parse dene
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Metin içinden JSON bloğu çıkarmayı dene
    try:
        clean = extract_json_from_text(text)
        return json.loads(clean)
    except (ValueError, json.JSONDecodeError) as exc:
        from src.utils.logging_utils import get_logger
        logger = get_logger(__name__)
        logger.warning("JSON parse başarısız: %s | Fallback kullanılıyor.", exc)
        return fallback


def dict_to_json_str(obj: Any, indent: int = 2) -> str:
    """Python nesnesini güzel biçimlendirilmiş JSON string'e dönüştürür."""
    return json.dumps(obj, ensure_ascii=False, indent=indent)
