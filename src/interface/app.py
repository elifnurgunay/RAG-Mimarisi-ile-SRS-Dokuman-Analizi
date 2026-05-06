import streamlit as st 
import pandas as pd
import sys
import os

# src klasöründeki modülleri içe aktarabilmek için yolu ekliyoruz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Arka uç mantığını yöneten SRSWorkflow sınıfını içe aktarıyoruz.
try:
    from src.interface.workflow import SRSWorkflow
except Exception as e:
    st.error(f"Sistem dosyaları yüklenemedi: {e}")

# Sayfa Ayarları
st.set_page_config(page_title="RE-Smart AI", layout="wide", page_icon="🤖")

# Sidebar ve Metrik CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] { width: 350px; }

    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    div[data-testid="stMetricLabel"] { font-size: 14px !important; color: #555; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- BAŞLIK ---
st.title("🤖 AI Destekli SRS Analiz Motoru")
st.markdown("Yazılım gereksinimlerindeki kalite hatalarını RAG mimarisi ile tespit edin 🚀")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("📂 SRS Dokümanı İşlemleri")
uploaded_file = st.sidebar.file_uploader("Analiz için PDF seçin", type=["pdf"])

# Analiz Butonu
analyze_button = st.sidebar.button("🔍 Analizi Başlat", type="primary", disabled=not uploaded_file)

# ANALİZ ÇALIŞTIRMA MANTIĞI

if analyze_button:
    with st.spinner("🚀 Analiz işlemi devam ediyor...."):
        if not os.path.exists("./data"): 
            os.makedirs("./data")
        
        temp_path = os.path.join("./data", uploaded_file.name)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Workflow modülünü başlat ve analizi tetikle
        workflow = SRSWorkflow()
        results = workflow.run_full_analysis(temp_path)
        
        if results:
            st.session_state['analysis_report'] = results["report"]
            st.session_state['cross_checks'] = results["cross_checks"]
            st.success("✅ Analiz ve Çapraz Kontrol Tamamlandı!")
        else:
            st.error("❌ Analiz başarısız oldu. Lütfen backend loglarını kontrol edin.")

# SONUÇLARIN GÖRSELLEŞTİRİLMESİ

if 'analysis_report' in st.session_state:
    report = st.session_state['analysis_report']
    
    # 1. ÜST METRİKLER
    st.subheader("📊 Yönetici Özeti")
    m1, m2, m3 = st.columns(3)
    m1.metric("📄 Doküman", report.document_name)
    m2.metric("📌 Durum", "Analiz Edildi")
    m3.metric("⚠️ Bulunan Hata", len(report.issues))

    st.markdown("---")

    # 2. RAG ÇELİŞKİ PANELİ (Maddeler Arası Mantıksal Zıtlıklar)
    if st.session_state.get('cross_checks'):
        with st.expander("🔗 RAG Çapraz Kontrol Bulguları (Çelişkiler)", expanded=True):
            for cc in st.session_state['cross_checks']:
                st.warning(f"**Gereksinim ID:** {cc['req_id']} | Bir çelişki tespit edildi!")
                st.info(f"**Tespit Nedeni:** {cc['reason']}")
                st.write(f"*Referans Metin:* {cc['conflict_with_text']}...")
                st.markdown("---")

    # 3. İSTATİSTİKSEL ANALİZ VE GRAFİKLER
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📉 Hata Tipi Dağılımı")
        
        all_types = ["Ambiguity", "Inconsistency", "Incompleteness", "Testability"]

        if report.issues:
            # Pydantic modellerini DataFrame'e dönüştürme
            df_issues = pd.DataFrame([i.model_dump() for i in report.issues])
            issue_counts = df_issues['type'].value_counts()
            
            issue_counts = issue_counts.reindex(all_types, fill_value=0)
            st.bar_chart(issue_counts)
        else:
            st.info("İstatistiksel veri üretilemedi.")

    with col_right:
        st.subheader("📋 Analiz Kapsamı")
        st.markdown("""
        - **ISO/IEC/IEEE 29148** Standart uyumluluğu taranıyor.
        - Maddeler arası **Anlamsal Çelişki** kontrolü yapılıyor.
        - **Test Edilebilirlik** kriterleri denetleniyor.
        """)

    st.markdown("---")

    # 4. DETAYLI PROBLEM TABLOSU
    st.subheader("📝 Tespit Edilen Problemler")
    if report.issues:
        df = pd.DataFrame([i.model_dump() for i in report.issues])
        
        df = df[["type", "problem", "suggestion"]]
        df.columns = ["Hata Tipi", "Problem Açıklaması", "Önerilen Çözüm"]

        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.balloons()
        st.success("Harika! Dokümanda hiçbir hata tespit edilmedi.")

    # 5. DIŞA AKTARMA (JSON)
    st.sidebar.markdown("---")
    st.sidebar.download_button(
        label="📥 Raporu JSON Olarak İndir",
        data=report.model_dump_json(indent=2),
        file_name=f"analiz_{report.document_name}.json",
        mime="application/json"
    )

else:
    st.info("👈 Lütfen sol taraftan bir SRS dokümanı yükleyin ve analizi başlatın.")
