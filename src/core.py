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
        text = self.extract_text_from_pdf(pdf_path)
        
        # Logic Gate for Noise Detection
        noise_words = ["camscanner", "scanned with", "pdf scanner"]
        is_only_noise = any(word in text.lower() for word in noise_words) and len(text) < 200

        # If the digital signal is weak or noisy, return a 'SWITCH_TO_VISION' flag
        if len(text.strip()) < 100 or is_only_noise:
            return self._extract_via_vision(pdf_path)
        
        # 1. DISCOVERY (Determining the 'Sensor' Range)
        discovery_prompt = """
        Analyze this industrial document. 
        IGNORE: Watermarks like 'CamScanner', 'PDF Scanner', or 'Metadata'.
        FOCUS: The header and main body of the technical document.
        Identify: 1. Doc Type, 2. Main Product Name, 3. UoM.
        Return ONLY JSON: {"type": "", "product": "", "uom": ""}
        """
        profile = self._call_llm(discovery_prompt, text[:2000], "llama-3.3-70b-versatile")
        
        # SAFETY CHECK: If discovery isn't a dict, use defaults to prevent crash
        if not isinstance(profile, dict):
            profile = {"type": "Document", "product": "Industrial Item", "uom": "units"}
        
        # 2. EXTRACTION (Dynamic Data Mapping)
        extract_prompt = f"""
        Extract numeric data from the MAIN TABLE only.
        STRICT RULES:
        1. Ignore any mention of 'CamScanner' or scanning software.
        2. If a customer name is not found, use 'General Client'.
        3. Ensure 'quantity' is a number. If found in a table, pick the column labeled 'Qty', 'Total', or 'Sqm'.
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
        """Robust Signal Decoder: Strips Markdown noise from JSON strings."""
        try:
            # Locate the actual JSON payload within the string
            start = content.find("[") if "[" in content else content.find("{")
            end = (content.rfind("]") + 1) if "]" in content else (content.rfind("}") + 1)
            
            if start == -1 or end == 0:
                return content # Return raw if no JSON markers found
                
            clean_json = content[start:end]
            return json.loads(clean_json)
        except Exception as e:
            return f"Decoder Fault: {str(e)} | Raw Content: {content[:100]}"

    # --- AUTHENTICATION ---

    def login(self, email, password):
        return self.supabase.auth.sign_in_with_password({"email": email, "password": password})

    def update_password(self, new_password):
        try:
            self.supabase.auth.update_user({"password": new_password})
            return "✅ Password updated successfully."
        except Exception as e:
            return f"❌ Update Failed: {str(e)}"