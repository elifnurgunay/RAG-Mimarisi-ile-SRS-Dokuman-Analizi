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

with st.sidebar.expander("Advanced Settings", expanded=False):
    model_mode = st.selectbox(
        "Model mode",
        options=[
            "Fast / Test - 8B",
            "Quality - 70B"
        ],
        index=0,
        help="Use 8B for faster and cheaper tests. Use 70B only for final quality checks."
    )

    model_name = (
        "llama-3.1-8b-instant"
        if model_mode == "Fast / Test - 8B"
        else "llama-3.3-70b-versatile"
    )

    run_conflict = st.checkbox("Run conflict analysis", value=False)

    top_k = st.slider(
        "Conflict top-k",
        min_value=1,
        max_value=5,
        value=1
    )

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
        final_report = workflow.run_full_analysis(
            temp_path,
            model_name=model_name,
            run_conflict=run_conflict,
            top_k=top_k,
        )
        
        if final_report:
            st.session_state['analysis_report'] = final_report
            st.success("✅ Analiz ve Çapraz Kontrol Tamamlandı!")
        else:
            st.error("❌ Analiz başarısız oldu. Lütfen backend loglarını kontrol edin.")

# SONUÇLARIN GÖRSELLEŞTİRİLMESİ

if 'analysis_report' in st.session_state:
    report = st.session_state['analysis_report']
    
    # 1. ÜST METRİKLER
    st.subheader("📊 Yönetici Özeti")
    
    # Custom summary text (skor içermeyen sade versiyon)
    if getattr(report, "language", "en") == "tr":
        summary_text = (
            f"'{report.document_name}' dokümanı analiz edildi. "
            f"Toplam {report.total_issues} aday kalite problemi "
            f"ve {report.total_conflicts} çelişki tespit edildi."
        )
    else:
        summary_text = (
            f"'{report.document_name}' was analyzed. "
            f"A total of {report.total_issues} candidate quality issue(s) "
            f"and {report.total_conflicts} conflict(s) were detected."
        )
    st.info(summary_text)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📄 Doküman", report.document_name)
    m2.metric("⚠️ Kalite Problemi", report.total_issues)
    m3.metric("🔗 Çelişki", report.total_conflicts)
    m4.metric("✅ Analiz Durumu", "Tamamlandı")

    st.markdown("---")

    # 2. RAG ÇELİŞKİ PANELİ (Maddeler Arası Mantıksal Zıtlıklar)
    if report.conflicts:
        with st.expander(f"🔗 RAG Çapraz Kontrol Bulguları ({len(report.conflicts)} Çelişki)", expanded=True):
            for cc in report.conflicts:
                st.warning(f"**Kaynak:** {cc.source_req_id} | Çelişki tespit edildi!")
                st.info(f"**Neden:** {cc.reason}")
                st.write(f"*Çelişen Metin:* {cc.conflict_with_text[:300]}...")
                st.markdown("---")

    # 3. İSTATİSTİKSEL ANALİZ VE GRAFİKLER
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📉 Problem Tipi Dağılımı")
        all_types = ["Ambiguity", "Inconsistency", "Incompleteness", "Testability"]

        if report.quality_issues:
            df_issues = pd.DataFrame([i.model_dump() for i in report.quality_issues])
            issue_counts = df_issues['type'].value_counts()
            issue_counts = issue_counts.reindex(all_types, fill_value=0)
            st.bar_chart(issue_counts)
        else:
            st.info("İstatistiksel veri üretilemedi.")

    with col_right:
        st.subheader("📋 Analiz Kapsamı")
        st.markdown(f"""
        - **ISO/IEC/IEEE 29148** Standart uyumluluğu.
        - **Hibrit RAG** tabanlı çelişki taraması.
        - **Groq LLM** ile anlamsal denetim.
        - **Analiz Tarihi:** {report.analysis_timestamp[:10]}
        """)

    st.markdown("---")

    # 4. DETAYLI PROBLEM TABLOSU
    st.subheader("📝 Tespit Edilen Aday Kalite Problemleri")
    if report.quality_issues:
        df = pd.DataFrame([i.model_dump() for i in report.quality_issues])
        df = df[["req_id", "type", "problem", "suggestion"]]
        df.columns = ["ID", "Problem Tipi", "Problem Açıklaması", "Önerilen Çözüm"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.balloons()
        st.success("Harika! Dokümanda hiçbir aday kalite problemi tespit edilmedi.")

    # 5. DIŞA AKTARMA (JSON)
    st.sidebar.markdown("---")
    st.sidebar.download_button(
        label="📥 Raporu JSON Olarak İndir",
        data=report.model_dump_json(indent=2),
        file_name=f"srs_analiz_{report.document_name}.json",
        mime="application/json"
    )

else:
    st.info("👈 Lütfen sol taraftan bir SRS dokümanı yükleyin ve analizi başlatın.")
