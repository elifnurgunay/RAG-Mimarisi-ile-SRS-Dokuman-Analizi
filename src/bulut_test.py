import sys

# --- SIHIRLI DOKUNUŞ: Python 3.14 Uyumluluk Yaması ---
# Hata veren kütüphane parçalarını devre dışı bırakıyoruz
class MockModule:
    def __getattr__(self, name):
        return MockModule() if name != '__iter__' else iter([])
    def __iter__(self):
        return iter([])
    def __call__(self, *args, **kwargs):
        return MockModule()

# pydantic.v1 ve alt modüllerini mock'layalım
sys.modules['pydantic.v1'] = MockModule()
sys.modules['pydantic.v1.errors'] = MockModule()
sys.modules['pydantic.v1.main'] = MockModule()
sys.modules['pydantic.v1.fields'] = MockModule()
sys.modules['pydantic.v1.validators'] = MockModule()
# --------------------------------------------------

# --- VENV KONTROLÜ ---
if sys.prefix == sys.base_prefix:
    print("⚠️ Uyarı: Sanal ortam (venv) aktif değil!")
    print("   Lütfen önce şunu çalıştırın: venv\\Scripts\\Activate.ps1")
    print("   Sonra bu script'i tekrar çalıştırın: python bulut_test.py")
    print("   Alternatif: Global ortamda çalıştırabilirsiniz ama pydantic hatası gelebilir.")
    exit(1)  # Zorunlu yapmak için aktif
# ---------------------

import os
from pathlib import Path
from dotenv import load_dotenv
from llama_index.llms.groq import Groq
from qdrant_client import QdrantClient

# .env dosyasını yükle (repo kök dizininde olmalı)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Çevresel değişkenlerden al
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not all([QDRANT_URL, QDRANT_API_KEY, GROQ_API_KEY]):
    raise RuntimeError(
        "Eksik çevresel değişken! .env içinde QDRANT_URL, QDRANT_API_KEY ve GROQ_API_KEY değerlerini belirleyin."
    )

print("\n🚀 Samet: Bulut altyapısı kontrol ediliyor (Python 3.14 Yaması Aktif)...")

try:
    # 1. Groq Testi
    print("🔄 Groq (Llama-3.3) test ediliyor...")
    llm = Groq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)
    response = llm.complete("Merhaba Samet abi, sistemin nihayet hazır!")
    print(f"🤖 Groq Yanıtı: {response}")

    # 2. Qdrant Testi
    print("\n🔄 Qdrant Cloud bağlantısı test ediliyor...")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    collections = client.get_collections()
    print("📦 Qdrant Bağlantısı: BAŞARILI!")
    
    print("\n✅ SPRINT 1 TAMAMLANDI! Yarın bu ekranı hocaya gösterebilirsin abi.")

except Exception as e:
    print(f"\n❌ Son bir pürüz: {e}")