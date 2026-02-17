import streamlit as st
import pandas as pd
from core import AvuxProcessor
import os

# 1. Boot System
avux = AvuxProcessor()

st.set_page_config(page_title="Avux Smart Intranet", layout="wide", page_icon="⚒️")

# 2. UI Aesthetics (Industrial Blue Theme)
st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #007BFF; color: white; border-radius: 5px; }
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚒️ Avux: Smart Intranet & Operations Ledger")

# 3. Sidebar Configuration
with st.sidebar:
    st.header("Control Panel")
    persona = st.selectbox("Active Persona", ["research", "marketing", "procurement", "finance", "content"])
    st.divider()
    st.write("System: Online")
    st.write("Database: Connected")

# 4. Input Channels
col1, col2 = st.columns(2)

with col1:
    st.subheader("📡 Primary Signal (PDF)")
    main_doc = st.file_uploader("Upload Specs or Ledger", type="pdf")

with col2:
    st.subheader("📑 Reference Channel")
    if persona == "content":
        ref_doc = st.file_uploader("Upload Template Document", type="pdf")
    else:
        st.info("Reference channel inactive for current persona.")

# 5. Operational Logic
if main_doc:
    # Save temp file for Poppler to read if scan
    with open("temp_input.pdf", "wb") as f:
        f.write(main_doc.getbuffer())

    # --- FINANCE WORKFLOW (DB Logging) ---
    if persona == "finance":
        if st.button("Extract Ledger Data"):
            with st.spinner("Processing Signal..."):
                records = avux.ingest_document("temp_input.pdf")
                if isinstance(records, list):
                    st.session_state['preview'] = records
                    st.success("Extraction Complete.")
                else:
                    st.error(f"Signal Fault: {records}")

        if 'preview' in st.session_state:
            st.table(pd.DataFrame(st.session_state['preview']))
            if st.button("✅ Commit to Supabase"):
                status = avux.save_to_ledger(st.session_state['preview'])
                st.info(status)
                if "Success" in status: del st.session_state['preview']

    elif persona == "finance":
        st.subheader("🏦 Operations Ledger Control")
        
        tab1, tab2 = st.tabs(["📥 Ingest New Data", "📊 Query History"])
        
        with tab1:
            if st.button("Extract & Preview Ledger Data"):
                # ... (keep your existing ingestion logic here)
                pass

        with tab2:
            st.info("Querying live data from Avux_Smart_Intranet")
            hist_query = st.text_input("Ask a question about historical orders (e.g., 'What is the total sqm for Zimplats?'):")
            if hist_query:
                with st.spinner("Accessing Historian..."):
                    answer = avux.query_ledger_history(hist_query)
                    st.success(answer)

    # --- CONTENT WORKFLOW (Synthesis) ---
    elif persona == "content" and ref_doc:
        main_text = avux.extract_text_from_pdf(main_doc) # Helper needed or direct extract
        ref_text = avux.extract_text_from_pdf(ref_doc)
        
        prompt = st.text_area("What should Avux generate?")
        if st.button("Synthesize"):
            res = avux.get_departmental_insight(f"SPECS: {main_text} TEMPLATE: {ref_text}", prompt, "content")
            st.markdown(res)

    # --- GENERAL RESEARCH/ANALYSIS WORKFLOW ---
    else:
        query = st.text_input(f"Inquiry for {persona.title()}:")
        if query:
            # We use extract_text here for simple RAG
            raw_text = avux.extract_text_from_pdf(main_doc) 
            res = avux.get_departmental_insight(raw_text, query, persona)
            st.markdown(f"### {persona.title()} Analysis\n{res}")

else:
    st.info("Awaiting Input Signal...")