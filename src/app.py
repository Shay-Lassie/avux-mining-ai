import streamlit as st
import pandas as pd
import plotly.express as px
from core import AvuxProcessor
from PIL import Image
import os

# ==========================================
# 1. SYSTEM BOOT & CONFIGURATION
# ==========================================
st.set_page_config(page_title="Avux Smart Intranet", layout="wide", page_icon="⚒️")

def load_css(file_path):
    if os.path.exists(file_path):
        with open(file_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Inject Avux Brand Identity
load_css("assets/style.css")

# Initialize the Processor (The PLC)
try:
    avux = AvuxProcessor()
except Exception as e:
    st.error(f"Hardware Link Fault: {e}")
    st.stop()

# ==========================================
# 2. SIDEBAR: AUTHENTICATION & NAVIGATION
# ==========================================
with st.sidebar:
    # Branding Logo
    if os.path.exists("assets/Logo1.png"):
        st.image("assets/Logo1.png", width=180)
    else:
        st.write("### AVUX")
    
    st.divider()
    st.header("🔐 Secure Access")
    
    if 'user' not in st.session_state:
        # LOGIN FORM (Input boxes styled dark via CSS)
        with st.form("login_gate"):
            e = st.text_input("Work Email")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                res = avux.login(e, p)
                if hasattr(res, 'user') and res.user:
                    st.session_state['user'] = res.user
                    st.rerun()
                else:
                    st.error("Access Denied: Invalid Credentials")
        
        # Stop execution here if not logged in (Security Interlock)
        st.stop()
    
    else:
        # LOGGED IN STATE
        st.write(f"👷 **Operator:** {st.session_state['user'].email}")
        if st.button("🚪 Sign Out"):
            del st.session_state['user']
            st.rerun()
        
        st.divider()
        st.header("Navigation Hub")
        persona = st.selectbox("Active Persona", 
                              ["finance", "auditor", "research", "content", "marketing", "procurement"])
        
        with st.expander("👤 Account Settings"):
            new_p = st.text_input("Update Password", type="password")
            if st.button("Apply Change"):
                st.info(avux.update_password(new_p))

# ==========================================
# 3. MAIN AREA: PERSONA LOGIC GATES
# ==========================================
st.title("⚒️ Avux: Research & Operations Ledger")

# --- PERSONA: FINANCE (UNIVERSAL LEDGER) ---
if persona == "finance":
    st.subheader("🏦 Universal Operations Ledger")
    
    # Pre-fetch Historian Data for Dashboard
    history = avux.get_ledger_history()
    
    t1, t2 = st.tabs(["📥 Ingest Data", "📊 Dashboard & Inquiry"])
    
    with t1:
        st.info("Upload a PO or DN. The system will auto-detect Product and Units.")
        f = st.file_uploader("Upload PDF", type="pdf", key="fin_up")
        if f:
            with open("tmp_fin.pdf", "wb") as tmp:
                tmp.write(f.getbuffer())
            if st.button("🔍 Run Avux Extraction"):
                with st.spinner("Analyzing Signal..."):
                    recs = avux.ingest_document("tmp_fin.pdf")
                    if isinstance(recs, list):
                        st.session_state['finance_pre'] = recs
                    else:
                        st.error(f"Signal Fault: {recs}")
        
        if 'finance_pre' in st.session_state:
            st.write("### 📝 Verification Ledger")
            # Editable table for Human-in-the-loop override
            edt = st.data_editor(pd.DataFrame(st.session_state['finance_pre']), num_rows="dynamic")
            if st.button("✅ Commit Verified Records"):
                res = avux.save_to_ledger(edt.to_dict('records'))
                st.success(res)
                del st.session_state['finance_pre']
                st.rerun()

    with t2:
        if history and len(history) > 0:
            df = pd.DataFrame(history)
            
            # KPI Metrics
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Thruput", f"{df['quantity'].sum():,.0f}")
            k2.metric("Total Records", len(df))
            k3.metric("System Status", "Online")

            st.divider()
            
            # Professional Plotly Chart
            fig = px.bar(df, x="product_name", y="quantity", color="status", barmode="group",
                         title="Product Fulfillment Summary",
                         color_discrete_map={"Delivered": "#84BD00", "Ordered": "#0072CE", "Processed": "#545454"})
            st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            q = st.text_input("💬 Ask the Historian (NL2SQL):")
            if q:
                st.markdown(avux.query_ledger_history(q))
        else:
            st.warning("📭 Historian is empty. Ingest data to view analytics.")

# --- PERSONA: AUDITOR (VENTILATION SPECIALIST) ---
elif persona == "auditor":
    st.subheader("🔦 Ventilation Audit Portal")
    
    # Mode Toggle: Airflow vs Tracer Gas
    audit_mode = st.radio("Select Audit Method", ["Volumetric Airflow", "Tracer Gas Concentration"])

    if audit_mode == "Tracer Gas Concentration":
        st.info("📊 Input Peak PPM from Gas Detector Nodes")
        col1, col2 = st.columns(2)
        ppm_intake = col1.number_input("Injected Concentration (PPM)", 1000, 10000, 5000)
        ppm_return = col2.number_input("Detected at Return Point (PPM)", 0, 10000, 3500)
        
        if ppm_intake > 0:
            recovery_rate = (ppm_return / ppm_intake) * 100
            leakage = 100 - recovery_rate
            st.metric("Gas Recovery Rate", f"{recovery_rate:.1f}%", delta=f"{leakage:.1f}% Leakage", delta_color="inverse")
            
            if leakage > 20:
                st.error(f"🚨 HIGH LEAKAGE DETECTED: {leakage:.1f}% gas loss between nodes.")
                if st.button("Generate Remediation Report"):
                    # We pass the physics metrics to the AI to write the technical steps
                    report_context = f"Tracer Audit: {ppm_intake} PPM in, {ppm_return} PPM out. Leakage {leakage}%."
                    report = avux.get_departmental_insight(report_context, "Write a remediation plan for this gas leakage.", "research")
                    st.markdown(report)

# --- PERSONA: RESEARCH (DOCS + VISION) ---
elif persona == "research":
    st.subheader("🔬 R&D Intelligence")
    t_doc, t_vis = st.tabs(["📄 Document Analysis", "📸 Equipment Inspection"])
    
    with t_doc:
        doc = st.file_uploader("Upload Tech Specs", type="pdf")
        if doc:
            q = st.text_input("Ask about technical constraints:")
            if q: st.write(avux.get_departmental_insight(avux.extract_text_from_pdf(doc), q, "research"))
            
    with t_vis:
        img = st.file_uploader("Upload Field Photo", type=['jpg', 'jpeg', 'png'])
        if img:
            st.image(img, width=400, caption="Equipment Source Signal")
            if st.button("🚀 Run Visual Fault Detection"):
                with st.spinner("Analyzing physical state..."):
                    st.write(avux.inspect_equipment(img.getvalue()))

# --- PERSONA: CONTENT (SYNTHESIS) ---
elif persona == "content":
    st.subheader("📑 Content Synthesis Engine")
    c1, c2 = st.columns(2)
    s = c1.file_uploader("New Specs PDF")
    t = c2.file_uploader("Reference Template PDF")
    if s and t:
        prompt = st.text_area("What should Avux generate?")
        if st.button("🚀 Synthesize"):
            res = avux.get_departmental_insight(f"SPECS: {avux.extract_text_from_pdf(s)} TEMP: {avux.extract_text_from_pdf(t)}", prompt, "content")
            st.write(res)

# --- DEFAULT CASE (Marketing/Procurement) ---
else:
    st.subheader(f"🔍 {persona.title()} Analysis")
    gen_doc = st.file_uploader(f"Upload document for {persona}")
    if gen_doc:
        gen_q = st.text_input(f"Question for {persona}:")
        if gen_q:
            st.write(avux.get_departmental_insight(avux.extract_text_from_pdf(gen_doc), gen_q, persona))