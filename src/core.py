import os
import json
import base64
from io import BytesIO
from dotenv import load_dotenv

# Signal Processing Libraries
from pypdf import PdfReader
from pdf2image import convert_from_path

# AI & Database Drivers
from groq import Groq
from supabase import create_client, Client

load_dotenv()

class AvuxProcessor:
    """
    AVUX CORE PROCESSOR
    Functions as the Central Control Unit (CCU) for the platform.
    """
    def __init__(self):
        # Initialize Power & Comms
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Connect to Data Historian (Supabase)
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Supabase Credentials Missing")
        self.supabase: Client = create_client(url, key)

    # --- INPUT STAGE: Auto-Ranging Ingestion ---
    
    def extract_text_from_pdf(self, pdf_path):
        """Standard Text Scraper (Digital Signal)"""
        text = ""
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                content = page.extract_text()
                if content: text += content
            return text
        except Exception as e:
            return f"Signal Error: {str(e)}"

    def ingest_document(self, pdf_path):
        """
        THE MASTER INGESTOR: 
        1. Detects Signal Quality (Text vs Vision)
        2. Discovers Engineering Profile (Product/UoM)
        3. Extracts via Universal Schema
        """
        # 1. Capture Raw Signal
        text = self.extract_text_from_pdf(pdf_path)
        
        # 2. Threshold Gate: If scan detected, use Vision Transducer
        if len(text.strip()) < 50:
            return self._extract_via_vision(pdf_path)
        
        # 3. Discovery Phase: Identify what we are looking at
        discovery_prompt = """
        Identify: 1. Doc Type (PO/DN), 2. Product (Fan/Seal/Gas Unit), 3. UoM (sqm/units).
        Return ONLY JSON: {"type": "", "product": "", "uom": ""}
        """
        profile_raw = self._call_llm(discovery_prompt, text[:2000], "llama-3.3-70b-versatile")
        
        # Ensure we have a clean dictionary
        profile = profile_raw if isinstance(profile_raw, dict) else {"type": "Document", "product": "Item", "uom": "units"}

        # 4. Universal Extraction Phase
        extract_prompt = f"""
        Extract data from this {profile.get('type')} into a JSON LIST.
        Schema: [{{
            "customer": "Name",
            "product_name": "{profile.get('product')}",
            "quantity": 0.0,
            "uom": "{profile.get('uom')}",
            "status": "Processed",
            "document_ref": "ID Number"
        }}]
        """
        return self._call_llm(extract_prompt, text, "llama-3.3-70b-versatile")

    def _extract_via_vision(self, pdf_path):
        """Vision extraction using Universal Schema for Scanned PDFs."""
        images = convert_from_path(pdf_path)
        img = images[0]
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        # Updated to Universal Schema
        prompt = """
        Extract data from this scan into a JSON LIST.
        Schema: [{"customer": "Name", "product_name": "Product", "quantity": 0.0, "uom": "sqm/units", "status": "Status", "document_ref": "ID"}]
        """
        
        completion = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }],
            temperature=0.0
        )
        return self._parse_json(completion.choices[0].message.content)

    # --- PROCESSING STAGE: Persona Routing ---

    def get_departmental_insight(self, context, question, persona):
        strict_rules = "STRICT: If irrelevant, return 'Invalid Query'. Temp 0.0. No rambling."
        personas = {
            "research": f"{strict_rules} You are a Senior R&D Engineer.",
            "marketing": f"{strict_rules} You are a Marketing Lead.",
            "procurement": f"{strict_rules} You are a BOM Specialist.",
            "finance": f"{strict_rules} You are an Auditor. Use the provided ledger history.",
            "content": f"{strict_rules} You are a Content Engine. Merge Data with Template."
        }
        system_msg = personas.get(persona, personas["research"])
        return self._call_llm(system_msg, f"CONTEXT: {context[:12000]}\n\nQUES: {question}", "llama-3.3-70b-versatile")

    # --- OUTPUT STAGE: Database & Historian ---

    def save_to_ledger(self, data_list):
        """Writes verified records to the UNIVERSAL_LEDGER DB."""
        try:
            # POINTING TO THE NEW UNIVERSAL TABLE
            self.supabase.table("universal_ledger").insert(data_list).execute()
            return "✅ Transmission Successful: Logged to Universal Ledger."
        except Exception as e:
            return f"❌ Bus Error: {str(e)}"

    def query_ledger_history(self, user_question):
        """Direct Historian Inquiry (NL2SQL Style)"""
        try:
            # POINTING TO THE NEW UNIVERSAL TABLE
            response = self.supabase.table("universal_ledger").select("*").execute()
            history_data = response.data
            
            if not history_data: return "Historian is empty."

            prompt = f"""
            You are the Avux Operations Auditor.
            CONTEXT: {json.dumps(history_data)}
            TASK: Summarize totals, quantities, and status per customer/product.
            """
            return self._call_llm(prompt, user_question, "llama-3.3-70b-versatile")
        except Exception as e:
            return f"Database Retrieval Fault: {str(e)}"

    def get_ledger_history(self):
        """Retrieves history for the Dashboard."""
        try:
            return self.supabase.table("universal_ledger").select("*").execute().data
        except:
            return None

    # --- HELPERS ---

    def _call_llm(self, system_prompt, user_content, model):
        completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model=model,
            temperature=0.0
        )
        content = completion.choices[0].message.content
        if "[" in content or "{" in content:
            return self._parse_json(content)
        return content

    def _parse_json(self, content):
        try:
            start = content.find("{") if "{" in content else content.find("[")
            end = (content.rfind("}") + 1) if "}" in content else (content.rfind("]") + 1)
            return json.loads(content[start:end])
        except:
            return f"Error Parsing JSON: {content}"

    # --- AUTHENTICATION ---

    def login(self, email, password):
        return self.supabase.auth.sign_in_with_password({"email": email, "password": password})

    def update_password(self, new_password):
        try:
            self.supabase.auth.update_user({"password": new_password})
            return "✅ Password updated successfully."
        except Exception as e:
            return f"❌ Update Failed: {str(e)}"