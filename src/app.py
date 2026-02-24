import streamlit as st
import pandas as pd
import plotly.express as px
from core import AvuxProcessor
from PIL import Image
import os

# --- 1. MANDATORY: FIRST COMMAND ---
st.set_page_config(page_title="Avux Smart Intranet", layout="wide", page_icon="⚒️")

# --- 2. BRANDING & STYLE ---
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css("assets/style.css")

# --- 3. INITIALIZE ENGINE ---
try:
    avux = AvuxProcessor()
except Exception as e:
    st.error(f"System Boot Failure: {e}")
    st.stop()

# --- 4. SIDEBAR BRANDING & AUTH ---
with st.sidebar:
    # Logic Fix: Check for Logo4 directly
    if os.path.exists("assets/Logo4.png"):
        st.image("assets/Logo4.png", use_container_width=True)
    else:
        st.warning("Logo4.png not found in assets/")
    
    st.divider()
    st.header("🔐 Secure Access")
    
    if 'user' not in st.session_state:
        with st.form("login_form"):
            email = st.text_input("Work Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                res = avux.login(email, pw)
                if hasattr(res, 'user') and res.user:
                    st.session_state['user'] = res.user
                    st.rerun()
                else:
                    st.error("Invalid Credentials.")
        st.stop() 
    else:
        st.write(f"👷 **Operator:** {st.session_state['user'].email}")
        if st.button("Sign Out"):
            del st.session_state['user']
            st.rerun()
        
        with st.expander("👤 Account Settings"):
            new_pw = st.text_input("New Password", type="password")
            if st.button("Update Password"):
                st.info(avux.update_password(new_pw))

    st.divider()
    st.header("Navigation")
    # Added 'auditor' to the personas
    persona = st.selectbox("Active Persona", ["research", "marketing", "procurement", "content", "finance", "auditor"])
    st.write(f"**Ledger:** Connected")

# --- 5. MAIN CONTENT ---
st.title("⚒️ Avux: Research & Operations Ledger")

# ==========================================
# FINANCE PERSONA
# ==========================================
if persona == "finance":
    st.subheader("🏦 Universal Operations Ledger")
    tab_ingest, tab_query = st.tabs(["📥 Ingest New PDF", "📊 Live Dashboard"])

    with tab_ingest:
        finance_file = st.file_uploader("Upload Document", type="pdf", key="fin_up")
        if finance_file:
            with open("temp_finance.pdf", "wb") as f:
                f.write(finance_file.getbuffer())
            if st.button("🔍 Run Extraction"):
                with st.spinner("Analyzing..."):
                    records = avux.ingest_document("temp_finance.pdf")
                    if isinstance(records, list):
                        st.session_state['finance_preview'] = records
         
            if 'finance_preview' in st.session_state:
                edited_df = st.data_editor(pd.DataFrame(st.session_state['finance_preview']), num_rows="dynamic")
                if st.button("✅ Commit to Ledger"):
                    status = avux.save_to_ledger(edited_df.to_dict('records'))
                    st.success(status)
                    if "✅" in status:
                        del st.session_state['finance_preview']
                        st.rerun()

    with tab_query:
        st.subheader("📈 Real-Time Operations Monitor")
        history = avux.get_ledger_history()
        if history:
            df = pd.DataFrame(history)
            
            # --- KPI Metrics ---
            k1, k2 = st.columns(2)
            k1.metric("Total Thruput", f"{df['quantity'].sum():,.0f} units")
            k2.metric("Records Found", len(df))

            # --- Plotly Chart ---
            fig = px.bar(df, x="product_name", y="quantity", color="status", barmode="group",
                         color_discrete_map={"Delivered": "#84BD00", "Ordered": "#0072CE"})
            st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            h_query = st.text_input("Query the history:")
            if h_query:
                st.markdown(avux.query_ledger_history(h_query))

# ==========================================
# AUDITOR PERSONA
# ==========================================
elif persona == "auditor":
    st.subheader("🔦 Ventilation Audit Portal")
    col1, col2, col3 = st.columns(3)
    q_in = col1.number_input("Intake Flow (m3/s)", 0.0)
    q_face = col2.number_input("Face Flow (m3/s)", 0.0)
    
    if q_in > 0:
        leakage = 100 - ((q_face/q_in)*100)
        if leakage > 20: st.error(f"Critical Leakage: {leakage:.1f}%")
        else: st.success(f"System Nominal: {leakage:.1f}% Leakage")
        
        if st.button("Generate Audit Report"):
            res = avux.get_departmental_insight(f"In:{q_in}, Face:{q_face}, Leakage:{leakage}%", "Generate remediation plan", "research")
            st.write(res)

# ==========================================
# CONTENT / OTHER PERSONAS
# ==========================================
elif persona == "content":
    st.subheader("📑 Content Synthesis Engine")
    c1, c2 = st.columns(2)
    spec = c1.file_uploader("Specs", type="pdf")
    temp = c2.file_uploader("Template", type="pdf")
    if spec and temp:
        prompt = st.text_area("Instructions")
        if st.button("Synthesize"):
            s_t = avux.extract_text_from_pdf(spec)
            t_t = avux.extract_text_from_pdf(temp)
            st.write(avux.get_departmental_insight(f"S:{s_t} T:{t_t}", prompt, "content"))

else:
    st.subheader(f"🔍 {persona.title()} Analysis")
    doc = st.file_uploader("Upload PDF", type="pdf")
    if doc:
        query = st.text_input("Question:")
        if query:
            raw = avux.extract_text_from_pdf(doc)
            st.write(avux.get_departmental_insight(raw, query, persona))