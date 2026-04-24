import streamlit as st
import pandas as pd
import sys
import os

# src klasöründeki modülleri içe aktarabilmek için yolu ekliyoruz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.analyzer import SRSAnalyzer, calculate_score

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="RE-Smart AI", layout="wide", page_icon="🤖")

# Sidebar ve genel stil CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] { width: 350px; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- ANALİZ MOTORUNU BAŞLAT ---
@st.cache_resource
def get_analyzer():
    return SRSAnalyzer()

analyzer = get_analyzer()

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
    with st.spinner("Llama-3 70B dokümanı analiz ediyor, lütfen bekleyin..."):
        sample_srs_text = """
        REQ-001: Sistem çok hızlı çalışmalıdır.
        REQ-002: Veritabanı verileri 2 yıl saklamalıdır.
        REQ-003: Arayüz modern ve şık olmalıdır.
        REQ-004: Sistem hata durumunda kullanıcıyı bilgilendirmelidir.
        """
        
        # ✅ DOĞRU FONKSİYON
        report = analyzer.analyze_text_with_score(sample_srs_text, doc_name=uploaded_file.name)
        
        if report:
            st.session_state['analysis_report'] = report
            st.success("✅ Analiz başarıyla tamamlandı!")
        else:
            st.error("❌ Analiz sırasında bir hata oluştu.")

# --- SONUÇLARI GÖSTER ---
if 'analysis_report' in st.session_state:
    report = st.session_state['analysis_report']
    
    # 1. ÜST METRİKLER
    st.subheader("📊 Genel Durum")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📄 Doküman", report.document_name)
    m2.metric("📌 Toplam Gereksinim", "Örnek Veri")
    m3.metric("⚠️ Bulunan Hata", len(report.issues))
    m4.metric("⭐ Kalite Skoru", f"%{report.overall_quality_score}")

    st.markdown("---")

    # 2. GRAFİK VE KALİTE ALANI
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📉 Hata Tipi Dağılımı")
        if report.issues:
            issue_counts = pd.DataFrame([i.dict() for i in report.issues])['type'].value_counts()
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

    # 3. DETAYLI TABLO
    st.subheader("📝 Tespit Edilen Problemler")
    if report.issues:
        df = pd.DataFrame([i.dict() for i in report.issues])
        
        df.columns = ["ID", "Hata Tipi", "Ciddiyet", "Problem Açıklaması", "Önerilen Çözüm"]

        def highlight_severity(val):
            color = ''
            if val == 'Critical': color = '#ff4b4b'
            elif val == 'High': color = '#ffa500'
            elif val == 'Medium': color = '#f1c40f'
            elif val == 'Low': color = '#2ecc71'
            return f'background-color: {color}; color: white; font-weight: bold'

        st.dataframe(df.style.applymap(highlight_severity, subset=['Ciddiyet']), use_container_width=True)
    else:
        st.balloons()
        st.success("Harika! Dokümanda hiçbir hata tespit edilmedi.")

    # 4. JSON İNDİRME
    st.sidebar.markdown("---")
    st.sidebar.download_button(
        label="📥 Raporu JSON Olarak İndir",
        data=report.model_dump_json(indent=2),  # ✅ FIX BURADA
        file_name=f"analiz_{report.document_name}.json",
        mime="application/json"
    )

else:
    st.info("👈 Lütfen sol taraftan bir SRS dokümanı yükleyin ve analizi başlatın.")