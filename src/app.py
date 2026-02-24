import streamlit as st
import pandas as pd
import plotly.express as px  # New: High-fidelity charts
from core import AvuxProcessor
from PIL import Image
import os

# --- 1. BRANDING & STYLE CONFIGURATION ---
def apply_custom_styling():
    st.markdown("""
        <style>
        /* Main background */
        .stApp { background-color: #fcfcfc; }
        
        /* Sidebar branding */
        [data-testid="stSidebar"] {
            background-color: #1a2a3a; /* Deep Navy Industrial */
            color: white;
        }
        
        /* Professional Buttons */
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            height: 3.5em;
            background-color: #007BFF;
            color: white;
            font-weight: 600;
            border: none;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background-color: #0056b3;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        /* Card-like containers for metrics */
        div[data-testid="stMetric"] {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border-left: 5px solid #007BFF;
        }
        </style>
    """, unsafe_allow_html=True)

# Boot System
avux = AvuxProcessor()
apply_custom_styling()

# Header with Logo
col_logo, col_text = st.columns([1, 4])
with col_logo:
    if os.path.exists("assets/logo.png"):
        logo = Image.open("assets/logo.png")
        st.image(logo, width=120)
with col_text:
    st.title("Avux Smart Intranet")
    st.caption("Industrial R&D and Operations Intelligence Platform")

# 1. INITIALIZE SYSTEM
try:
    avux = AvuxProcessor()
except Exception as e:
    st.error(f"System Boot Failure: {e}")
    st.stop()

st.set_page_config(page_title="Avux Smart Intranet", layout="wide", page_icon="⚒️")

# Industrial UI Styling
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; background-color: #007BFF; color: white; border-radius: 5px; height: 3em; font-weight: bold; }
    .stTab { font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚒️ Avux: Research & Operations Ledger")

# 2. SIDEBAR: AUTHENTICATION & NAVIGATION
with st.sidebar:
    st.header("🔐 Avux Secure Access")
    
    if 'user' not in st.session_state:
        st.info("Please sign in to access system data.")
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
        st.stop() # Stops execution if not logged in
    
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
    st.header("Navigation Hub")
    persona = st.selectbox("Active Persona", ["research", "marketing", "procurement", "content", "finance"])
    st.write(f"**Database:** Universal Ledger (Connected)")

# 3. MAIN PROCESSING LOGIC

# ==========================================
# BRANCH A: FINANCE & UNIVERSAL LEDGER
# ==========================================
if persona == "finance":
    st.subheader("🏦 Universal Operations Ledger")
    tab_ingest, tab_query = st.tabs(["📥 Ingest New PDF", "📊 Live Dashboard & Inquiry"])

    with tab_ingest:
        st.info("Extract data from POs or DNs. AI will auto-detect Product and Units.")
        finance_file = st.file_uploader("Upload Document", type="pdf", key="fin_up")
        
        if finance_file:
            with open("temp_finance.pdf", "wb") as f:
                f.write(finance_file.getbuffer())
            
            if st.button("🔍 Run Extraction Pipeline"):
                with st.spinner("Analyzing Signal..."):
                    # This uses our 'Auto-Ranging' Ingestor (Text or Vision)
                    records = avux.ingest_document("temp_finance.pdf")
                    if isinstance(records, list):
                        st.session_state['finance_preview'] = records
                    else:
                        st.error(f"Extraction Error: {records}")
         
            if 'finance_preview' in st.session_state:
                st.write("### 📝 Verify Records")
                # editable table for manual override
                edited_df = st.data_editor(pd.DataFrame(st.session_state['finance_preview']), num_rows="dynamic")
                
                if st.button("✅ Commit to Universal Ledger"):
                    with st.spinner("Transmitting..."):
                        status = avux.save_to_ledger(edited_df.to_dict('records'))
                        st.success(status)
                        if "✅" in status:
                            del st.session_state['finance_preview']
                            st.rerun()

    with tab_query:
        # 1. LIVE ANALYTICS (The 'Dashboard' mode)
        st.subheader("📈 Real-Time Operations Monitor")
        history = avux.get_ledger_history()
        if history:
            df_all = pd.DataFrame(history)
            
            # Universal Metric: Group by Product and Status
            # This handles Seals(sqm) and Fans(units) simultaneously
            metrics = df_all.groupby(['product_name', 'status'])['quantity'].sum().reset_index()
            
            col_a, col_b = st.columns([1, 2])
            with col_a:
                st.write("**Summary Table**")
                st.dataframe(metrics, hide_index=True)
            with col_b:
                st.write("**Product Volume per Status**")
                # A bar chart that shows the breakdown
                st.bar_chart(data=metrics, x='product_name', y='quantity', color='status')
        else:
            st.warning("Database Historian is empty.")

        st.divider()
        # 2. NATURAL LANGUAGE INQUIRY (The 'Chat' mode)
        st.subheader("💬 Ask the Historian")
        h_query = st.text_input("Query the database history:", placeholder="e.g. Total quantity of fans delivered to Zimplats?")
        if h_query:
            with st.spinner("Analyzing History..."):
                st.markdown(avux.query_ledger_history(h_query))

# ==========================================
# BRANCH B: CONTENT SYNTHESIS
# ==========================================
elif persona == "content":
    st.subheader("📑 Content Synthesis Engine")
    col1, col2 = st.columns(2)
    with col1: spec_doc = st.file_uploader("Upload Specs (Signal)", type="pdf")
    with col2: temp_doc = st.file_uploader("Upload Template (Structure)", type="pdf")

    if spec_doc and temp_doc:
        instructions = st.text_area("Generation Instructions:")
        if st.button("🚀 Synthesize"):
            s_text = avux.extract_text_from_pdf(spec_doc)
            t_text = avux.extract_text_from_pdf(temp_doc)
            st.write(avux.get_departmental_insight(f"DATA: {s_text} TEMPLATE: {t_text}", instructions, "content"))

# ==========================================
# BRANCH C: RESEARCH / MARKETING / PROCUREMENT
# ==========================================
else:
    st.subheader(f"🔍 {persona.title()} Analysis")
    doc = st.file_uploader(f"Upload PDF", type="pdf")
    if doc:
        query = st.text_input(f"Question for {persona.title()}:")
        if query:
            # We use ingest_document even here so that it can handle scanned Research papers!
            with open("temp_gen.pdf", "wb") as f: f.write(doc.getbuffer())
            with st.spinner("Analyzing..."):
                raw_text = avux.extract_text_from_pdf(doc) # Fallback to text for chat context
                st.write(avux.get_departmental_insight(raw_text, query, persona))