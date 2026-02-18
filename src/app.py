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
         
            # Verification Stage (The 'Set-Point Override')
            if 'finance_preview' in st.session_state:
                st.write("### 📝 Verify & Edit Records")
                st.info("The AI couldn't find some SQM values. Please enter them manually in the table below before saving.")
                
                # Use data_editor instead of table/dataframe
                edited_df = st.data_editor(
                    pd.DataFrame(st.session_state['finance_preview']),
                    num_rows="dynamic",
                    key="ledger_editor"
                )
                
                if st.button("✅ Commit Verified Data to Ledger"):
                    with st.spinner("Transmitting to Supabase..."):
                        # We convert the edited dataframe back to a list of dicts
                        verified_records = edited_df.to_dict('records')
                        status = avux.save_to_ledger(verified_records)
                        st.success(status)
                        if "✅" in status:
                            del st.session_state['finance_preview']
                            st.rerun() # Refresh to update the graph

    with tab_query:
        st.info("Mode: Direct Inquiry. Query the cloud database without a document.")
        h_query = st.text_input("Ask a question about historical data:")
        if h_query:
            with st.spinner("Accessing Database Historian..."):
                answer = avux.query_ledger_history(h_query)
                st.markdown(f"**Avux Financial Analysis:**\n\n{answer}")
            with tab_query:
                st.info("Mode: Direct Inquiry & Analytics")
        
                # 1. NEW FEATURE: Live Analytics Dashboard
                if st.checkbox("📈 Show Live Operations Dashboard"):
                    with st.spinner("Fetching DB metrics..."):
                        history = avux.get_ledger_history() # You'll need to add this to core.py
                        if history:
                            df_all = pd.DataFrame(history)
                            
                            # Create the Chart Metrics
                            metrics = df_all.groupby('status')['sqm_delivered'].sum().reset_index()
                            
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.metric("Total Sqm Delivered (Global)", f"{df_all['sqm_delivered'].sum():,.2f}")
                                st.dataframe(metrics)
                            with col_b:
                                # Recreating the chart from your image
                                st.bar_chart(data=metrics, x='status', y='sqm_delivered')
                
                # 2. Keep your existing NL2SQL query below the dashboard
                st.divider()
                h_query = st.text_input("Ask a specific question about historical data:")
                # ... (rest of your query logic)

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