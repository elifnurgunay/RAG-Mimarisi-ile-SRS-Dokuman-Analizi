import streamlit as st
import pandas as pd

# Sidebar genişliğini artırmak için CSS
st.markdown("""
<style>
/* Sidebar genişliği */
[data-testid="stSidebar"] {
    width: 350px;
}

/* File uploader kutusuna stil */
[data-testid="stFileUploader"] {
    border: 2px dashed #4CAF50;
    padding: 10px;
    border-radius: 10px;
    background-color: #f9f9f9;
}
</style>
""", unsafe_allow_html=True)

# Sayfa ayarları
st.set_page_config(page_title="RE-Smart AI", layout="wide")

# Demo modu
demo_mode = True

# Başlık
st.title("🤖 RE-Smart: AI Destekli SRS Analiz Motoru")
st.markdown("Akıllı gereksinim analizi ile hataları erken tespit edin 🚀")
st.markdown("---")

st.sidebar.markdown("<br><br><br><br>", unsafe_allow_html=True)
# Sidebar upload alanı
st.sidebar.header("📂 SRS Dokümanı Yükle")
uploaded_file = st.sidebar.file_uploader("PDF seç", type=["pdf"])

# Demo çalıştır
if uploaded_file or demo_mode:

    st.success("✅ Analiz tamamlandı")

    doc_name = uploaded_file.name if uploaded_file else "demo_srs.pdf"
    total_req = 42
    total_issues = 12
    quality_score = 72

    # Üst metrikler
    st.subheader("📊 Genel Durum")
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("📄 Doküman", doc_name)
    col2.metric("📌 Gereksinim", total_req)
    col3.metric("⚠️ Hata", total_issues)
    col4.metric("⭐ Kalite Skoru", f"%{quality_score}")

    st.markdown("---")

    # Grafik alanı
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📉 Hata Dağılımı")

        chart_data = pd.DataFrame({
            "Hata Tipi": ["Belirsizlik", "Çelişki", "Test Edilebilirlik"],
            "Sayı": [5, 3, 2]
        })

        st.bar_chart(chart_data.set_index("Hata Tipi"))

    with col_right:
        st.subheader("📈 Kalite Skoru")

        st.progress(quality_score / 100)

        if quality_score > 80:
            st.success("Kalite seviyesi yüksek")
        elif quality_score > 50:
            st.warning("Orta kalite, iyileştirilebilir")
        else:
            st.error("Düşük kalite! Kritik iyileştirme gerekli")

    st.markdown("---")

    # Detay tablo
    st.subheader("📝 Tespit Edilen Problemler")

    data = {
        "ID": ["REQ-005", "REQ-012", "REQ-028", "REQ-033", "REQ-040"],
        "Hata": ["Belirsizlik", "Çelişki", "Test Edilebilirlik", "Eksiklik", "Belirsizlik"],
        "Severity": ["Orta", "Kritik", "Düşük", "Kritik", "Orta"],
        "Açıklama": [
            "‘Hızlı olmalı’ ifadesi ölçülemez.",
            "REQ-045 ile çelişiyor.",
            "Test kriteri yok.",
            "Security eksik.",
            "Standart belirtilmemiş."
        ]
    }

    df = pd.DataFrame(data)

    def highlight(row):
        if row["Severity"] == "Kritik":
            return ["background-color: #ff4b4b"] * len(row)
        elif row["Severity"] == "Orta":
            return ["background-color: #ffa500"] * len(row)
        else:
            return ["background-color: #2ecc71"] * len(row)

    st.dataframe(df.style.apply(highlight, axis=1), use_container_width=True)

else:
    st.warning("👈 Soldan PDF yükleyin")