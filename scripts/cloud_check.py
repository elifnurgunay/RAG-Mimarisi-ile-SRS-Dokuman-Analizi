"""
tests/bulut_test.py

Groq ve Qdrant Cloud bağlantılarını doğrulayan hızlı sağlık kontrolü.
Kullanım: .venv/Scripts/python.exe tests/bulut_test.py
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_groq import ChatGroq
from qdrant_client import QdrantClient
from src.config import GROQ_API_KEY, QDRANT_URL, QDRANT_API_KEY, validate

# Kritik anahtarları doğrula
try:
    validate()
except ValueError as e:
    print(f"❌ Konfigürasyon hatası: {e}")
    sys.exit(1)

print("\n🚀 Bulut altyapısı kontrol ediliyor...")

try:
    # 1. Groq Testi
    print("🔄 Groq (Llama-3.3-70b) test ediliyor...")
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=GROQ_API_KEY,
        temperature=0,
    )
    response = llm.invoke("Merhaba! Sistem hazır mı?")
    print(f"🤖 Groq Yanıtı: {response.content[:80]}...")

    # 2. Qdrant Testi
    print("\n🔄 Qdrant Cloud bağlantısı test ediliyor...")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    collections = client.get_collections()
    col_names = [c.name for c in collections.collections]
    print(f"📦 Qdrant Bağlantısı: BAŞARILI! Koleksiyonlar: {col_names}")

    print("\n✅ Tüm bulut bağlantıları başarıyla doğrulandı.")

except Exception as e:
    print(f"\n❌ Hata: {e}")
    sys.exit(1)

