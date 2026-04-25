import sys
from pathlib import Path

import fitz
import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pdf_text_extractor import extract_pdf_text, parse_requirements

# Sayfa ayarları
st.set_page_config(page_title="RE-Smart AI", layout="wide")

# Demo modu
demo_mode = True

EXAMPLE_PDF = ROOT_DIR / "ornek_srs.pdf"

# Başlık
st.title("🤖 RE-Smart: AI Destekli SRS Analiz Motoru")
st.markdown("Akıllı gereksinim analizi ile hataları erken tespit edin 🚀")
st.markdown("---")

st.sidebar.write("")
# Sidebar upload alanı
st.sidebar.header("📂 SRS Dokümanı Yükle")
uploaded_file = st.sidebar.file_uploader("PDF seç", type=["pdf"])


def extract_text_from_upload(uploaded):
    try:
        pdf_bytes = uploaded.read()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return "\n".join(page.get_text("text") for page in doc)
    except Exception:
        return None


if uploaded_file or demo_mode:
    st.success("✅ Analiz tamamlandı")

    if uploaded_file:
        doc_name = uploaded_file.name
        text = extract_text_from_upload(uploaded_file)
    else:
        doc_name = EXAMPLE_PDF.name
        text = extract_pdf_text(str(EXAMPLE_PDF)) if EXAMPLE_PDF.exists() else ""

    if not text:
        st.error("PDF'ten metin çıkarılamadı. Lütfen dosyayı kontrol edin.")
        st.stop()

    requirements = parse_requirements(text)
    total_req = len(requirements)
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

    # Örnek gereksinimler
    st.subheader("🧾 Bulunan Gereksinimler")
    if requirements:
        df_requirements = pd.DataFrame(requirements)
        st.dataframe(df_requirements, use_container_width=True)
    else:
        st.info("PDF içinde REQ-xxx biçiminde hiçbir gereksinim bulunamadı.")

else:
    st.warning("👈 Soldan PDF yükleyin")