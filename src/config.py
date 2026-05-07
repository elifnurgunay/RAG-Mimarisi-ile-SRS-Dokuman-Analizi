"""
src/config.py

Merkezi konfigürasyon yöneticisi.
.env dosyası TEK BURADAN okunur; diğer modüller bu modülü import eder.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Proje kökü (src/config.py → src/ → proje kökü)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# .env yükle (override=True → ortam değişkenleri .env ile güncellenir)
load_dotenv(ENV_PATH, override=True)


# ---------------------------------------------------------------------------
# API Anahtarları
# ---------------------------------------------------------------------------
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
QDRANT_URL: str = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

# ---------------------------------------------------------------------------
# Model Ayarları
# ---------------------------------------------------------------------------
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "llama-3.3-70b-versatile")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# ---------------------------------------------------------------------------
# Vektör Veritabanı Ayarları
# ---------------------------------------------------------------------------
QDRANT_COLLECTION_NAME: str = os.getenv(
    "QDRANT_COLLECTION_NAME", "elif_logic_collection"
)
EMBEDDING_MODEL_NAME: str = os.getenv(
    "EMBEDDING_MODEL_NAME", "BAAI/bge-m3"
)


# ---------------------------------------------------------------------------
# İşleme Parametreleri
# ---------------------------------------------------------------------------
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))
TOP_K: int = int(os.getenv("TOP_K", "3"))
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "5000"))  # karakter cinsinden

# ---------------------------------------------------------------------------
# Doğrulama: Kritik anahtarlar eksikse erken uyarı ver
# ---------------------------------------------------------------------------
def validate() -> None:
    """Kritik ayarları doğrular; eksikse ValueError fırlatır."""
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not QDRANT_URL:
        missing.append("QDRANT_URL")
    if not QDRANT_API_KEY:
        missing.append("QDRANT_API_KEY")
    if missing:
        raise ValueError(
            f".env dosyasında şu değişkenler eksik: {', '.join(missing)}\n"
            f"Kontrol edilen dosya: {ENV_PATH}"
        )
