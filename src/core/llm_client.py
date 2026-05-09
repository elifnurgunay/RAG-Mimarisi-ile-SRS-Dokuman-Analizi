"""
src/core/llm_client.py

Groq LLM nesnesini merkezi olarak üreten fabrika modülü.
Her dosyada ayrı ayrı ChatGroq(...) oluşturmak yerine
bu modül kullanılır → model değişikliği tek yerden yapılır.
"""
from langchain_groq import ChatGroq
from langchain_core.language_models.chat_models import BaseChatModel

from src.config import GROQ_API_KEY, LLM_MODEL_NAME, LLM_TEMPERATURE
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Varsayılan retry politikası (langchain-groq rate limit yönetimi)
# ---------------------------------------------------------------------------
_DEFAULT_MAX_RETRIES = 1
_DEFAULT_REQUEST_TIMEOUT = 60  # saniye


def get_llm(
    model: str = LLM_MODEL_NAME,
    temperature: float = LLM_TEMPERATURE,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    timeout: int = _DEFAULT_REQUEST_TIMEOUT,
) -> BaseChatModel:
    """
    Yapılandırılmış bir ChatGroq LLM nesnesi döndürür.

    Args:
        model:       Kullanılacak Groq model adı.
        temperature: Örnekleme sıcaklığı (0.0 = deterministik).
        max_retries: Rate-limit / geçici hata için max deneme sayısı.
        timeout:     HTTP istek zaman aşımı (saniye).

    Returns:
        Hazır ChatGroq nesnesi.

    Raises:
        ValueError: GROQ_API_KEY eksikse.
    """
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY bulunamadı! "
            "Lütfen .env dosyasını kontrol edin (src/config.py üzerinden okunur)."
        )

    logger.info(
        "LLM başlatılıyor | model=%s | temperature=%.1f | max_retries=%d",
        model,
        temperature,
        max_retries,
    )

    return ChatGroq(
        model=model,
        temperature=temperature,
        groq_api_key=GROQ_API_KEY,
        max_retries=max_retries,
        request_timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Hazır singleton — sık kullanılan varsayılan LLM örneği
# ---------------------------------------------------------------------------
# Modülü import eden kod `from src.core.llm_client import default_llm` ile
# doğrudan kullanabilir. Her import'ta yeniden oluşturulmaz.
def get_default_llm() -> BaseChatModel:
    """Varsayılan ayarlarla bir LLM nesnesi döndürür (lazy init)."""
    return get_llm()
