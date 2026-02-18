import streamlit as st
import pandas as pd
import os
from core import AvuxProcessor

# 1. INITIALIZE SYSTEM COMPONENTS
# Equivalent to booting the PLC and checking comms
try:
    avux = AvuxProcessor()
except Exception as e:
    st.error(f"System Boot Failure: {e}")
    st.stop()

# 2. HMI CONFIGURATION (Display Settings)
st.set_page_config(page_title="Avux Smart Intranet", layout="wide", page_icon="⚒️")

# Industrial Blue Theme Injection
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; background-color: #007BFF; color: white; border-radius: 5px; height: 3em; font-weight: bold; }
    .stTab { font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚒️ Avux: Research & Operations Ledger")

# 3. SIDEBAR: NAVIGATION & CONTROL
with st.sidebar:
    st.header("Navigation Hub")
    persona = st.selectbox("Active Persona", 
                          ["research", "marketing", "procurement", "content", "finance"])
    st.divider()
    st.write(f"**Current Role:** {persona.upper()}")
    st.write("**Database:** Avux_Smart_Intranet (Connected)")
    st.write("**Inference:** Groq Llama-3.3-70b")

# 4. MAIN PROCESSING LOGIC (The Logic Gates)

# ==========================================
# BRANCH A: THE FINANCE LEDGER (Tabbed Interface)
# ==========================================
if persona == "finance":
    st.subheader("🏦 Operations Ledger Control")
    tab_ingest, tab_query = st.tabs(["📥 Ingest New PDF", "📊 Query Historian"])

    with tab_ingest:
        st.info("Mode: Operational Entry. Upload a scan or digital log to update the database.")
        finance_file = st.file_uploader("Upload Delivery Note / Ledger PDF", type="pdf", key="fin_up")
        
        if finance_file:
            # Save temp file for the Vision Transducer to read if necessary
            with open("temp_finance.pdf", "wb") as f:
                f.write(finance_file.getbuffer())
            
            if st.button("🔍 Run Extraction Pipeline"):
                with st.spinner("Avux is analyzing the signal..."):
                    # Use the 'Ingest Document' master function from core.py
                    records = avux.ingest_document("temp_finance.pdf")
                    
                    if isinstance(records, list):
                        st.session_state['finance_preview'] = records
                        st.success("Signal Processed Successfully.")
                    else:
                        st.error(f"Extraction Error: {records}")

            # Verification Stage (Holding Relay)
            if 'finance_preview' in st.session_state:
                st.write("### Data Preview (Verify before committing)")
                df_preview = pd.DataFrame(st.session_state['finance_preview'])
                st.table(df_preview)
                
                if st.button("✅ Commit to Permanent Ledger"):
                    with st.spinner("Transmitting to Supabase..."):
                        status = avux.save_to_ledger(st.session_state['finance_preview'])
                        st.success(status)
                        # Clear memory after successful write
                        if "✅" in status:
                            del st.session_state['finance_preview']

    with tab_query:
        st.info("Mode: Direct Inquiry. Query the cloud database without a document.")
        h_query = st.text_input("Ask a question about historical data:")
        if h_query:
            with st.spinner("Accessing Database Historian..."):
                answer = avux.query_ledger_history(h_query)
                st.markdown(f"**Avux Financial Analysis:**\n\n{answer}")

# ==========================================
# BRANCH B: CONTENT SYNTHESIS (Dual-Channel Input)
# ==========================================
elif persona == "content":
    st.subheader("📑 Content Synthesis Engine")
    col1, col2 = st.columns(2)
    
    with col1:
        spec_doc = st.file_uploader("Upload New Specs (Signal)", type="pdf")
    with col2:
        temp_doc = st.file_uploader("Upload Template (Structure)", type="pdf")

    if spec_doc and temp_doc:
        st.divider()
        instructions = st.text_area("What should Avux synthesize?", 
                                   placeholder="e.g., Generate a proposal based on these specs following the template layout.")
        if st.button("🚀 Generate Content"):
            with st.spinner("Merging Signal & Structure..."):
                # Extract text for both
                s_text = avux.extract_text_from_pdf(spec_doc)
                t_text = avux.extract_text_from_pdf(temp_doc)
                context = f"SPECS: {s_text}\n\nTEMPLATE: {t_text}"
                
                response = avux.get_departmental_insight(context, instructions, "content")
                st.markdown("### Generated Result")
                st.write(response)

# ==========================================
# BRANCH C: GENERAL ANALYSIS (Research, Marketing, Procurement)
# ==========================================
else:
    st.subheader(f"🔍 {persona.title()} Analysis")
    doc = st.file_uploader(f"Upload document for {persona} analysis", type="pdf")
    
    if doc:
        query = st.text_input(f"Question for {persona.title()} Assistant:")
        if query:
            with st.spinner("Calculating..."):
                raw_text = avux.extract_text_from_pdf(doc)
                response = avux.get_departmental_insight(raw_text, query, persona)
                st.markdown(f"### {persona.title()} Response")
                st.write(response)
    else:
        st.info(f"Awaiting {persona} input signal...")