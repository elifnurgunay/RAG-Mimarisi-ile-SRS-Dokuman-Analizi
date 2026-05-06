import sys
import os
from pathlib import Path
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

from src.parsing.chunking_strategy import ReqChunkingStrategy
from src.infrastructure.search_optimization import SearchOptimizer

# .env dosyasını yükle
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path, override=True)

class SRSRetriever:
    def __init__(self, collection_name="elif_logic_collection"):
        self.collection_name = collection_name
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.url = os.getenv("QDRANT_URL")
        self.api_key = os.getenv("QDRANT_API_KEY")
        self.vector_store = None
        self.optimizer = SearchOptimizer() # Hibrit arama için optimizer ekliyoruz

    def load_and_index_pdf(self, pdf_path):
        """PDF'i yükler, parçalar ve Qdrant'a indexler."""
        if not os.path.exists(pdf_path):
            print(f"Hata: {pdf_path} dosyasi bulunamadi!")
            return False

        print(f"Dosya yukleniyor: {pdf_path}")
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()

        self.chunk_strategy = ReqChunkingStrategy(
            req_pattern=r"(REQ\s*[-.]?\s*\d+|GEREKSINIM\s*[-.]?\s*\d+|R\s*[-._]?\s*\d+)",
            fallback_chunk_size=500,
            fallback_overlap=50,
        )
        texts = self.chunk_strategy.chunk_documents(documents)
        print(f"Metin parcalari olusturuldu: {len(texts)} (REQ-ID bazli chunking)")

        print(f"Qdrant'a yukleniyor (Koleksiyon: {self.collection_name})...")
        self.vector_store = QdrantVectorStore.from_documents(
            texts,
            self.embeddings,
            url=self.url,
            api_key=self.api_key,
            collection_name=self.collection_name,
            force_recreate=True,
            prefer_grpc=False
        )
        print("Indexleme tamamlandi!")
        return True

    def add_structured_data(self, requirements_json: list):
        """Bera'dan gelen temizlenmiş veriyi (ID ve metin) indexler."""
        Document = None
        try:
            from langchain_core.documents import Document
        except ImportError:
            try:
                from langchain.schema import Document
            except ImportError:
                Document = None

        docs = []
        for req in requirements_json:
            if Document is not None:
                doc = Document(
                    page_content=req["text"],
                    metadata={"req_id": req["id"]}
                )
            else:
                doc = {"page_content": req["text"], "metadata": {"req_id": req["id"]}}
            docs.append(doc)

        print(f"{len(docs)} adet yapilandirilmis gereksinim ekleniyor...")
        if not self.vector_store:
            self.vector_store = QdrantVectorStore.from_documents(
                docs,
                self.embeddings,
                url=self.url,
                api_key=self.api_key,
                collection_name=self.collection_name,
                force_recreate=False,
                prefer_grpc=False
            )
        else:
            self.vector_store.add_documents(docs)
        print("Yapilandirilmis veri basariyla eklendi!")

    def get_all_documents(self):
        """Koleksiyondaki tüm dokümanları getirir."""
        if not self.vector_store:
            self.vector_store = QdrantVectorStore.from_existing_collection(
                embedding=self.embeddings,
                collection_name=self.collection_name,
                url=self.url,
                api_key=self.api_key,
                prefer_grpc=False
            )
        
        return self.vector_store.similarity_search("", k=100)

    def get_similar_requirements(self, query, top_k=3):
        """
        Hibrit Arama: Verilen sorguya en benzer gereksinimleri 
        BM25 ve Vektör skoru harmanlayarak getirir.
        """
        if not self.vector_store:
            self.vector_store = QdrantVectorStore.from_existing_collection(
                embedding=self.embeddings,
                collection_name=self.collection_name,
                url=self.url,
                api_key=self.api_key,
                prefer_grpc=False
            )

        print(f"Hibrit sorgu yapiliyor: '{query}'")
        
        # 1. Aşama: Vektör veritabanından geniş bir aday listesi çek (Dense Search)
        # top_k'dan daha fazla çekiyoruz ki BM25 ile rerank yapabilelim.
        candidates = self.vector_store.similarity_search(query, k=top_k * 4)
        
        if not candidates:
            return []

        # 2. Aşama: BM25 + Dense Harmanlama (Hybrid Reranking)
        # Aday metinlerini listeye çevir
        candidate_texts = [doc.page_content for doc in candidates]
        
        # SearchOptimizer kullanarak hibrit skorları hesapla
        # hybrid_search metodu indeksleri ve skorları döndürür.
        hybrid_results = self.optimizer.hybrid_search(
            query=query,
            documents=candidate_texts,
            top_k=top_k,
            bm25_weight=0.4, # Kelime eşleşmesi ağırlığı
            dense_weight=0.6  # Anlamsal yakınlık ağırlığı
        )
        
        # 3. Aşama: Hibrit sonuçları Document objelerine geri dönüştür
        final_docs = []
        for idx, score in hybrid_results:
            doc = candidates[idx]
            # Skoru metadata'ya ekle (opsiyonel)
            doc.metadata["hybrid_score"] = score
            final_docs.append(doc)
            
        return final_docs

if __name__ == "__main__":
    retriever = SRSRetriever()
    
    # GÜN 2 TESTİ: Yapılandırılmış (Gerçek) Veri Simülasyonu
    gercek_veri = [
        {"id": "REQ-004", "text": "Sistem verileri 30 gun boyunca yedeklemelidir."},
        {"id": "REQ-005", "text": "Yedekleme islemi her gece saat 02:00'da baslamalidir."}
    ]
    
    retriever.add_structured_data(gercek_veri)
    results = retriever.get_similar_requirements("Yedekleme ne zaman yapilir?")
    
    for res in results:
        print(f"ID: {res.metadata.get('req_id')} | Icerik: {res.page_content}")
