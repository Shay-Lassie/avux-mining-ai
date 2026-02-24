# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from core import AvuxProcessor
from PIL import Image
import os

# 1. BOOT SEQUENCE
st.set_page_config(page_title="Avux Smart Intranet", layout="wide", page_icon="⚒️")

def load_css(file):
    if os.path.exists(file):
        with open(file) as f: st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

try:
    avux = AvuxProcessor()
except Exception as e:
    st.error(f"Boot Failure: {e}"); st.stop()

# 2. SIDEBAR & AUTH
with st.sidebar:
    if os.path.exists("assets/Logo4.png"): st.image("assets/Logo4.png", width=180)
    st.header("🔐 Secure Access")
    if 'user' not in st.session_state:
        with st.form("login"):
            e = st.text_input("Work Email"); p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                res = avux.login(e, p)
                if hasattr(res, 'user'): st.session_state['user'] = res.user; st.rerun()
                else: st.error("Denied.")
        st.stop()
    else:
        st.write(f"👷 {st.session_state['user'].email}")
        if st.button("Sign Out"): del st.session_state['user']; st.rerun()
        persona = st.selectbox("Persona", ["finance", "auditor", "research", "content", "marketing"])

# 3. MAIN DASHBOARD
st.title("⚒️ Avux: Research & Operations Ledger")

if persona == "finance":
    t1, t2 = st.tabs(["📥 Ingest Data", "📊 Dashboard & Query"])
    with t1:
        f = st.file_uploader("Upload PDF")
        if f:
            with open("tmp.pdf","wb") as tmp: tmp.write(f.getbuffer())
            if st.button("🔍 Extract"):
                recs = avux.ingest_document("tmp.pdf")
                if isinstance(recs, list): st.session_state['pre'] = recs
        if 'pre' in st.session_state:
            edt = st.data_editor(pd.DataFrame(st.session_state['pre']))
            if st.button("✅ Save to Ledger"):
                st.info(avux.save_to_ledger(edt.to_dict('records')))
                del st.session_state['pre']; st.rerun()
    with t2:
        hist = avux.get_ledger_history()
        if hist:
            df = pd.DataFrame(hist)
            k1, k2 = st.columns(2)
            k1.metric("Total Qty", f"{df['quantity'].sum():,.0f}")
            k2.metric("Records", len(df))
            fig = px.bar(df, x="product_name", y="quantity", color="status", color_discrete_map={"Delivered":"#84BD00","Ordered":"#0072CE"})
            st.plotly_chart(fig, use_container_width=True)
            q = st.text_input("Ask the Historian:")
            if q: st.markdown(avux.query_ledger_history(q))

elif persona == "auditor":
    st.subheader("🔦 Ventilation Audit Dashboard")
    c1, c2 = st.columns(2)
    q_in = c1.number_input("Intake Flow (m3/s)", 0.0)
    q_fa = c2.number_input("Face Flow (m3/s)", 0.0)
    if q_in > 0:
        leak = 100 - ((q_fa/q_in)*100)
        st.metric("Leakage Rate", f"{leak:.1f}%", delta=f"{leak:.1f}%", delta_color="inverse")
        if st.button("Generate Remediation"):
            st.write(avux.get_departmental_insight(f"Leak:{leak}%", "Plan steps", "research"))

elif persona == "research":
    t_doc, t_vis = st.tabs(["📄 Doc Analysis", "📸 Equipment Inspection"])
    with t_doc:
        doc = st.file_uploader("Upload Specs")
        if doc:
            q = st.text_input("Query Specs:")
            if q: st.write(avux.get_departmental_insight(avux.extract_text_from_pdf(doc), q, "research"))
    with t_vis:
        img = st.file_uploader("Upload Photo", type=['jpg','png'])
        if img:
            st.image(img, width=400)
            if st.button("🚀 Inspect"):
                st.write(avux.inspect_equipment(img.getvalue()))

elif persona == "content":
    c1, c2 = st.columns(2)
    s = c1.file_uploader("Specs")
    t = c2.file_uploader("Template")
    if s and t:
        ins = st.text_area("Instructions")
        if st.button("Synthesize"):
            st.write(avux.get_departmental_insight(f"S:{avux.extract_text_from_pdf(s)} T:{avux.extract_text_from_pdf(t)}", ins, "content"))