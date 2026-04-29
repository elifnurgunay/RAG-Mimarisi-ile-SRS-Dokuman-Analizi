import sys
import os
from dotenv import load_dotenv

# --- SIHIRLI DOKUNUŞ V2: Geliştirilmiş Python 3.14 Yaması ---
class DummyClass:
    pass

class MockModule:
    def __getattr__(self, name):
        return DummyClass  
    def __call__(self, *args, **kwargs):
        return DummyClass()

sys.modules['pydantic.v1'] = MockModule()
sys.modules['pydantic.v1.errors'] = MockModule()
sys.modules['pydantic.v1.main'] = MockModule()
sys.modules['pydantic.v1.fields'] = MockModule()
sys.modules['pydantic.v1.validators'] = MockModule()
# --------------------------------------------------

from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

from src.chunking_strategy import ReqChunkingStrategy

# 1. Çevresel Değişkenleri Yükle (.env dosyasındaki API keyler vb.)
load_dotenv()

class RAGCore:
    def __init__(self):
        # Yeni HuggingFace kütüphanesini kullanıyoruz
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.chunk_strategy = ReqChunkingStrategy(
            req_pattern=r"(REQ-\d{3,})",
            fallback_chunk_size=1000,
            fallback_overlap=200,
        )

    def process_document(self, file_path):
        """PDF dosyasını yükler ve parçalara ayırır."""
        print(f"📄 Dosya yükleniyor: {file_path}")
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        texts = self.chunk_strategy.chunk_documents(documents)
        print(f"✅ Metin {len(texts)} parçaya bölündü. (REQ-ID bazlı chunking kullanıldı)")
        
        print("☁️ Qdrant Bulutuna yükleniyor... (Bu işlem PDF'in boyutuna göre biraz sürebilir)")
        
        # Yeni QdrantVectorStore kütüphanesini kullanıyoruz
        qdrant = QdrantVectorStore.from_documents(
            texts,
            self.embeddings,
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
            collection_name="srs_dokumanlari",
            force_recreate=True, 
            prefer_grpc=False  # Bulut için en güvenli bağlantı yolu budur
        )
        print("✅ Vektör veritabanı başarıyla hazırlandı ve buluta yüklendi!")
        return qdrant

# --- TEST ETMEK İÇİN ---
if __name__ == "__main__":
    pdf_dosya_yolu = "data/teletas_srs_arastirma.pdf" 
    rag = RAGCore()
    rag.process_document(pdf_dosya_yolu)