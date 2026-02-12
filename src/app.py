import streamlit as st
import pandas as pd
from core import AvuxProcessor
import os

# Initialize Engine
avux = AvuxProcessor()

st.set_page_config(page_title="Avux Mining PA", layout="wide", page_icon="⚒️")

# --- CUSTOM CSS FOR INDUSTRIAL LOOK ---
st.markdown("""
    <style>
    .main { background-color: #f5f5f5; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007BFF; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚒️ Avux: Research & Operations Ledger")

# --- SIDEBAR ---
with st.sidebar:
    st.header("System Controls")
    persona = st.selectbox("Select Active Persona", 
                          ["research", "marketing", "procurement", "finance", "content"])
    st.divider()
    st.write("**Model:** Llama-3.3-70b")
    st.write("**Mode:** Deterministic (Temp 0.0)")

# --- INPUT AREA ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📡 Primary Signal")
    main_doc = st.file_uploader("Upload Product Specs / Ledger PDF", type="pdf")

with col2:
    st.subheader("📑 Reference Channel")
    if persona == "content":
        ref_doc = st.file_uploader("Upload Template / Proposal Structure", type="pdf")
    else:
        st.info("Reference channel inactive for this persona.")
        ref_doc = None

# --- EXECUTION LOGIC ---
if main_doc:
    # Read primary text
    main_text = avux.extract_text_from_pdf(main_doc)
    
    st.divider()
    
    # CASE 1: Content Synthesis (Two Files)
    if persona == "content":
        if ref_doc:
            ref_text = avux.extract_text_from_pdf(ref_doc)
            combined_context = f"TECHNICAL SPECS:\n{main_text}\n\nTEMPLATE:\n{ref_text}"
            
            prompt = st.text_area("Content Instructions:", placeholder="e.g. Generate a proposal for Zimplats using the template structure...")
            if st.button("Synthesize Content"):
                with st.spinner("Processing..."):
                    res = avux.get_departmental_insight(combined_context, prompt, "content")
                    st.markdown(res)
        else:
            st.warning("Please upload a Reference Template for synthesis.")

    # CASE 2: Analysis (One File)
    else:
        query = st.text_input(f"Enter {persona.title()} Query:", placeholder="Ask a specific question...")
        if query:
            with st.spinner("Analyzing..."):
                res = avux.get_departmental_insight(main_text, query, persona)
                st.markdown(f"### {persona.title()} Analysis")
                st.write(res)

else:
    st.info("Awaiting input signal. Please upload a document in the Primary Signal channel.")