Bu proje, yazılım gereksinim dokümanlarını (SRS) otomatik olarak analiz etmek, gereksinim kalitesini artırmak ve ISO/IEC/IEEE 29148 standartlarına göre belirsizlik/çelişki tespiti yapmak için oluşturulmuş bir Retrieval-Augmented Generation (RAG) pipeline'ıdır. 
📌 İçindekiler
Proje Hakkında
Özellikler
Mimari
Dosya Yapısı
Kurulum ve Çalıştırma
Başarı Metrikleri
Geliştirici Notları
1. Proje HakkındaGeleneksel manuel analiz süreçlerindeki "Bilişsel Yükü" azaltmayı hedefleyen RE-Smart, dokümanları anlamsal parçalara ayırarak bir Vektör Veritabanında saklar ve yapay zeka yardımıyla denetler. Hedef Kullanıcı: İş Analistleri, Sistem Mimarları ve QA Takımları. Temel Standart: ISO 29148 (Gereksinim Mühendisliği).
2. Özellikler
Yapısal Parçalama (Structural Chunking): REQ-ID bazlı 92 ayrı parçaya bölme işlemi. Hibrit Arama (Hybrid Search): BM25 (anahtar kelime) ve Vektör (anlam) tabanlı aramanın LangChain ile birleştirilmesi. Metadata Traceability: Her bulgunun sayfa numarası ve gereksinim ID'si ile eşleşmesi. Yüksek Performanslı LLM: Groq LPU üzerinden Llama-3.3-70b ile saniyeler içinde analiz. Kullanıcı Dostu UI: Streamlit tabanlı, ≤ 3 tıklama ile rapor sunan dashboard.
3. Mimari
Proje, uçtan uca bir RAG pipeline'ı üzerine kuruludur:Veri Girişi: PDF formatındaki SRS dokümanı yüklenir. Önişleme: PyMuPDF ve Regex desenleri (REQ-\d+) ile metin ayrıştırılır. Vektörleştirme: all-MiniLM-L6-v2 modeliyle 384 boyutlu embedding oluşturulur. Depolama: Qdrant Cloud üzerinde metadata zenginleştirilmiş indeksleme. Retrieval & Generation: LangChain aracılığıyla bağlam çekilir ve LLM analiz raporu üretilir. 
4. Kurulum ve Çalıştırma
Gereksinimler
Python 3.11+
Aktif bir .env dosyası (QDRANT_URL, API_KEY vb.)
Adımlar
Sanal ortamı oluşturun ve paketleri yükleyin:
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
Bulut bağlantısını test edin:
python src/bulut_test.py [cite: 171]
Arayüzü başlatın:
streamlit run ui/app.py [cite: 106]
5. Başarı Metrikleri
Hız: 20 sayfalık analiz < 10 saniye.
Hassasiyet: %150ms altında Qdrant sorgu gecikmesi.
Doğruluk: %95+ metin çıkarımı başarısı.
6. Geliştirici Notları
Regex Zorluğu: Bozuk PDF formatlarında REQ başlıklarını yakalamak için Samet ile birlikte "Pair Review" yapılmıştır.
JSON Zorunluluğu: LLM çıktıları Pydantic ile kesin JSON formatına zorlanmıştır. 
Hazırlayanlar: 10. Grup - RE-Smart Ekibi 
