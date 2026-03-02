import streamlit as st
import pandas as pd
import plotly.express as px
from core import AvuxProcessor
from PIL import Image
import os

# --- 1. BOOT SEQUENCE (Mandatory First) ---
st.set_page_config(page_title="Avux Smart Intranet", layout="wide", page_icon="⚒️")

@st.cache_resource
def get_engine():
    return AvuxProcessor()

avux = get_engine()

def load_css(file_path):
    if os.path.exists(file_path):
        with open(file_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

# --- 2. SIDEBAR & AUTH ---
with st.sidebar:
    if os.path.exists("assets/Logo4.png"): st.image("assets/Logo4.png", width=180)
    st.divider()
    st.header("🔐 Secure Access")
    if 'user' not in st.session_state:
        with st.form("login"):
            e = st.text_input("Work Email")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                res = avux.login(e, p)
                if hasattr(res, 'user'): 
                    st.session_state['user'] = res.user
                    st.rerun()
                else: st.error("Access Denied.")
        st.stop()
    else:
        st.write(f"👷 {st.session_state['user'].email}")
        if st.button("🚪 Sign Out"): 
            del st.session_state['user']
            st.rerun()
        persona = st.selectbox("Navigation Hub", ["finance", "auditor", "research", "content", "marketing"])

# --- 3. MAIN AREA ---
st.title("⚒️ Avux: Research & Operations Ledger")

if persona == "finance":
    st.subheader("🏦 Universal Operations Ledger")
    # Cache DB calls to improve speed
    @st.cache_data(ttl=600)
    def fetch_data(): return avux.get_ledger_history()
    history = fetch_data()
    
    t1, t2 = st.tabs(["📥 Ingest Data", "📊 Dashboard & Inquiry"])
    with t1:
        f = st.file_uploader("Upload Delivery Note / PO", type="pdf")
        if f:
            with open("tmp.pdf","wb") as tmp: tmp.write(f.getbuffer())
            if st.button("🔍 Run Avux Extraction"):
                with st.spinner("Analyzing..."):
                    recs = avux.ingest_document("tmp.pdf")
                    if isinstance(recs, list): st.session_state['pre'] = recs
        
        if 'pre' in st.session_state:
            edt = st.data_editor(pd.DataFrame(st.session_state['pre']), num_rows="dynamic")
            if st.button("✅ Commit Verified Records"):
                res = avux.save_to_ledger(edt.to_dict('records'))
                if "✅" in res:
                    st.success(res)
                    st.cache_data.clear() # Clear cache so chart updates
                    del st.session_state['pre']
                    st.rerun()
                else: st.error(res)

    with t2:
        if history:
            df = pd.DataFrame(history)
            k1, k2 = st.columns(2)
            k1.metric("Total Volume", f"{df['quantity'].sum():,.0f}")
            k2.metric("System Health", "Operational")
            fig = px.bar(df, x="product_name", y="quantity", color="status", barmode="group",
                         color_discrete_map={"Delivered":"#84BD00","Ordered":"#0072CE"})
            st.plotly_chart(fig, use_container_width=True)
            q = st.text_input("💬 Ask the Historian:")
            if q: st.markdown(avux.query_ledger_history(q))
        else: st.warning("Historian is empty.")

elif persona == "auditor":
    st.subheader("🔦 Ventilation Audit Portal")
    col1, col2 = st.columns(2)
    q_in = col1.number_input("Injected PPM", 0.0)
    q_fa = col2.number_input("Detected PPM", 0.0)
    if q_in > 0:
        leak = 100 - ((q_fa / q_in) * 100)
        st.metric("Leakage Rate", f"{leak:.1f}%", delta=f"{leak:.1f}%", delta_color="inverse")
        if st.button("Generate Remediation Report"):
            st.write(avux.get_departmental_insight(f"Leak:{leak}%", "Write remediation plan", "research"))

elif persona == "research":
    t_doc, t_vis = st.tabs(["📄 Doc Analysis", "📸 Equipment Inspection"])
    with t_doc:
        doc = st.file_uploader("Upload Specs")
        if doc:
            q = st.text_input("Ask about technical constraints:")
            if q: st.write(avux.get_departmental_insight(avux.extract_text_from_pdf(doc), q, "research"))
    with t_vis:
        img = st.file_uploader("Upload Photo", type=['jpg','png','jpeg'])
        if img:
            st.image(img, width=400)
            if st.button("🚀 Inspect"):
                st.write(avux.inspect_equipment(img.getvalue()))