import streamlit as st
import pandas as pd
import plotly.express as px
from core import AvuxProcessor
import os

# 1. BOOT & CACHING
st.set_page_config(page_title="Avux Smart Intranet", layout="wide", page_icon="⚒️")

@st.cache_resource
def get_engine(): return AvuxProcessor()
avux = get_engine()

if os.path.exists("assets/style.css"):
    with open("assets/style.css") as f: st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 2. SIDEBAR COMMAND CENTER
with st.sidebar:
    if os.path.exists("assets/Logo4.png"): st.image("assets/Logo4.png", width=180)
    st.header("🔐 Secure Access")
    
    if 'user' not in st.session_state:
        with st.form("login"):
            e = st.text_input("Work Email")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                res = avux.login(e, p)
                if isinstance(res, str) and "AUTH_ERROR" in res: st.error("Invalid Credentials")
                elif hasattr(res, 'user'): st.session_state['user'] = res.user; st.rerun()
        st.stop()
    else:
        st.write(f"👷 {st.session_state['user'].email}")
        if st.button("🚪 Sign Out"): del st.session_state['user']; st.rerun()
        persona = st.selectbox("Navigation Hub", ["finance", "auditor", "research", "content", "marketing", "procurement"])

# 3. MAIN DASHBOARD
st.title("⚒️ Avux: Research & Operations Ledger")

if persona == "finance":
    st.subheader("🏦 Universal Operations Ledger")
    @st.cache_data(ttl=300)
    def fetch_history(): return avux.get_ledger_history()
    history = fetch_history()

    t1, t2 = st.tabs(["📥 Ingest Data", "📊 Dashboard & Inquiry"])
    with t1:
        f = st.file_uploader("Upload PDF", type="pdf")
        if f:
            with open("tmp.pdf","wb") as tmp: tmp.write(f.getbuffer())
            if st.button("🔍 Run Avux Extraction"):
                with st.spinner("Extracting..."):
                    recs = avux.ingest_document("tmp.pdf")
                    if isinstance(recs, list): st.session_state['pre'] = recs
        if 'pre' in st.session_state:
            edt = st.data_editor(pd.DataFrame(st.session_state['pre']), num_rows="dynamic")
            if st.button("✅ Commit Verified Records"):
                res = avux.save_to_ledger(edt.to_dict('records'))
                if "✅" in res:
                    st.success(res); st.cache_data.clear(); del st.session_state['pre']; st.rerun()
                else: st.error(res)
    with t2:
        if history:
            df = pd.DataFrame(history)
            c1, c2 = st.columns(2)
            c1.metric("Total Volume", f"{df['quantity'].sum():,.0f}")
            c2.metric("System Health", "Operational")
            fig = px.bar(df, x="product_name", y="quantity", color="status", barmode="group",
                         color_discrete_map={"Delivered":"#84BD00","Ordered":"#0072CE"})
            st.plotly_chart(fig, use_container_width=True)
            q = st.text_input("💬 Ask the Historian:")
            if q: st.markdown(avux.query_ledger_history(q))
        else: st.warning("Historian is empty.")

elif persona == "auditor":
    st.subheader("🔦 Ventilation Audit Portal")
    m = st.radio("Method", ["Airflow", "Tracer Gas"])
    col1, col2 = st.columns(2)
    if m == "Tracer Gas":
        q_in = col1.number_input("Injected PPM", 0.0); q_fa = col2.number_input("Detected PPM", 0.0)
        if q_in > 0:
            leak = 100 - ((q_fa / q_in) * 100)
            st.metric("Leakage Rate", f"{leak:.1f}%", delta=f"{leak:.1f}%", delta_color="inverse")
            if st.button("Generate Report"): st.write(avux.get_departmental_insight(f"Leak:{leak}%", "Steps", "research"))

elif persona == "research":
    t1, t2 = st.tabs(["📄 Doc Analysis", "📸 Equipment Inspection"])
    with t1:
        doc = st.file_uploader("Upload Specs")
        if doc:
            q = st.text_input("Question:")
            if q: st.write(avux.get_departmental_insight(avux.extract_text_from_pdf(doc), q, "research"))
    with t2:
        img = st.file_uploader("Upload Photo", type=['jpg','png','jpeg'])
        if img:
            st.image(img, width=400)
            if st.button("🚀 Inspect"): st.write(avux.inspect_equipment(img.getvalue()))

elif persona == "content":
    c1, c2 = st.columns(2)
    s = c1.file_uploader("Specs"); t = c2.file_uploader("Template")
    if s and t:
        ins = st.text_area("Instructions")
        if st.button("Synthesize"):
            st.write(avux.get_departmental_insight(f"S:{avux.extract_text_from_pdf(s)} T:{avux.extract_text_from_pdf(t)}", ins, "content"))