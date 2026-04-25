import streamlit as st
import pandas as pd
import sys
import os

# src klasöründeki modülleri içe aktarabilmek için yolu ekliyoruz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Modülleri yükle
try:
    from src.workflow import SRSWorkflow
except Exception as e:
    st.error(f"Sistem dosyaları yüklenemedi: {e}")

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="RE-Smart AI", layout="wide", page_icon="🤖")

# Profesyonel Sidebar ve Metrik CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] { width: 350px; }

    /* Metric kutusu */
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* METRIC BAŞLIK (Doküman, Durum vs) */
    div[data-testid="stMetricLabel"] {
        font-size: 12px !important;
        color: #666;
    }

    /* METRIC DEĞER (asıl büyük yazı) */
    div[data-testid="stMetricValue"] {
        font-size: 18px !important;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- BAŞLIK ---
st.title("🤖 RE-Smart: AI Destekli SRS Analiz Motoru")
st.markdown("Akıllı gereksinim analizi ile hataları erken tespit edin 🚀")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("📂 SRS Dokümanı İşlemleri")
uploaded_file = st.sidebar.file_uploader("Analiz için PDF seçin", type=["pdf"])

# Analiz Butonu
analyze_button = st.sidebar.button("🔍 Analizi Başlat", type="primary", disabled=not uploaded_file)

# --- ANALİZ MANTIĞI ---
if analyze_button:
    with st.spinner("🚀 RAG Mimarisi ve Llama-3 çalışıyor, lütfen bekleyin..."):
        if not os.path.exists("./data"): os.makedirs("./data")
        temp_path = os.path.join("./data", uploaded_file.name)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # WORKFLOW ÇALIŞTIR
        workflow = SRSWorkflow()
        results = workflow.run_full_analysis(temp_path)
        
        if results:
            st.session_state['analysis_report'] = results["report"]
            st.session_state['cross_checks'] = results["cross_checks"]
            st.success("✅ Analiz ve Çapraz Kontrol Tamamlandı!")
        else:
            st.error("❌ Analiz başarısız oldu. Terminali kontrol edin.")

# --- SONUÇLARI GÖSTER ---
if 'analysis_report' in st.session_state:
    report = st.session_state['analysis_report']
    
    # 1. ÜST METRİKLER (4 Kolonlu Eski Yapı)
    st.subheader("📊 Yönetici Özeti")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📄 Doküman", report.document_name)
    m2.metric("📌 Durum", "Analiz Edildi")
    m3.metric("⚠️ Bulunan Hata", len(report.issues))
    m4.metric("⭐ Kalite Skoru", f"%{report.overall_quality_score}")

    st.markdown("---")

    # YENİ: RAG ÇELİŞKİ PANELİ (Görseli bozmadan araya ekledik)
    if st.session_state.get('cross_checks'):
        with st.expander("🔗 RAG Çapraz Kontrol Bulguları (Çelişkiler)", expanded=True):
            for cc in st.session_state['cross_checks']:
                st.warning(f"**Gereksinim ID:** {cc['req_id']} | **Çelişen Metin:** {cc['conflict_with_text']}...")
                st.info(f"**Tespit Nedeni:** {cc['reason']}")
                st.markdown("---")

    # 2. GRAFİK VE KALİTE ALANI (2 Kolonlu Eski Yapı)
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📉 Hata Tipi Dağılımı")
        if report.issues:
            # Pydantic v2 uyumlu model_dump kullanımı
            issue_counts = pd.DataFrame([i.model_dump() for i in report.issues])['type'].value_counts()
            st.bar_chart(issue_counts)
        else:
            st.write("Hiç hata bulunamadı! 🌟")

    with col_right:
        st.subheader("📈 Kalite Değerlendirmesi")
        st.progress(report.overall_quality_score / 100)
        
        score = report.overall_quality_score
        if score > 80:
            st.success(f"Puan: {score} - Doküman kalitesi yüksek.")
        elif score > 50:
            st.warning(f"Puan: {score} - Orta seviye, iyileştirme önerilir.")
        else:
            st.error(f"Puan: {score} - Düşük kalite! Kritik hatalar mevcut.")

    st.markdown("---")

    # 3. DETAYLI RENKLİ TABLO (Eski Sevdiğin Stil)
    st.subheader("📝 Tespit Edilen Problemler")
    if report.issues:
        df = pd.DataFrame([i.model_dump() for i in report.issues])
        df.columns = ["ID", "Hata Tipi", "Ciddiyet", "Problem Açıklaması", "Önerilen Çözüm"]

        # Eski Stil Renklendirme Fonksiyonu
        def highlight_severity(row):
            color = ''
            if row["Ciddiyet"] == 'Critical': color = 'background-color: #ff4b4b; color: white;'
            elif row["Ciddiyet"] == 'High': color = 'background-color: #ffa500; color: white;'
            elif row["Ciddiyet"] == 'Medium': color = 'background-color: #f1c40f; color: black;'
            elif row["Ciddiyet"] == 'Low': color = 'background-color: #2ecc71; color: white;'
            return [color] * len(row)

        st.dataframe(df.style.apply(highlight_severity, axis=1), use_container_width=True)
    else:
        st.balloons()
        st.success("Harika! Dokümanda hiçbir hata tespit edilmedi.")

    # 4. JSON İNDİRME (Sidebar'a Geri Döndü)
    st.sidebar.markdown("---")
    st.sidebar.download_button(
        label="📥 Raporu JSON Olarak İndir",
        data=report.model_dump_json(indent=2),
        file_name=f"analiz_{report.document_name}.json",
        mime="application/json"
    )

else:
    st.info("👈 Lütfen sol taraftan bir SRS dokümanı yükleyin ve analizi başlatın.")