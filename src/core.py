# core.py
import os, json, base64
from io import BytesIO
from dotenv import load_dotenv
from pypdf import PdfReader
from pdf2image import convert_from_path
from groq import Groq
from supabase import create_client, Client

load_dotenv()

class AvuxProcessor:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    def extract_text_from_pdf(self, pdf_path):
        text = ""
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                content = page.extract_text()
                if content: text += content
        except: pass
        return text

    def ingest_document(self, pdf_path):
        text = self.extract_text_from_pdf(pdf_path)
        if len(text.strip()) < 100 or "camscanner" in text.lower():
            return self._extract_via_vision(pdf_path)
        
        discovery_prompt = "Identify: 1. Doc Type (PO/DN), 2. Product, 3. UoM (sqm/units). Return ONLY JSON: {\"type\": \"\", \"product\": \"\", \"uom\": \"\"}"
        profile = self._call_llm(discovery_prompt, text[:2000], "llama-3.3-70b-versatile")
        
        if not isinstance(profile, dict): 
            profile = {"type": "Document", "product": "Item", "uom": "units"}
        
        # We explicitly tell the AI to use the keys that match our SQL columns
        extract_prompt = f"""
        Extract data from this {profile.get('type')} into a JSON LIST.
        USE THESE EXACT KEYS: "customer", "product_name", "quantity", "uom", "status", "document_ref"
        Value for product_name: {profile.get('product')}
        Value for uom: {profile.get('uom')}
        STRICT: quantity must be a number only.
        """
        return self._call_llm(extract_prompt, text, "llama-3.3-70b-versatile")

    def save_to_ledger(self, data_list):
        """Standardizes and commits data to Supabase."""
        try:
            # CLEANING SIGNAL: Ensure 'quantity' is a float to match SQL float8
            for row in data_list:
                try:
                    row['quantity'] = float(row.get('quantity', 0))
                except:
                    row['quantity'] = 0.0
            
            # TRANSMIT
            res = self.supabase.table("universal_ledger").insert(data_list).execute()
            
            # LOG TO TERMINAL (For your eyes only)
            print(f"DEBUG: Successfully inserted {len(data_list)} rows.")
            return "✅ Transmission Successful."
        except Exception as e:
            print(f"DATABASE ERROR: {str(e)}") # Check your terminal!
            return f"❌ Bus Error: {str(e)}"
        
    def _extract_via_vision(self, pdf_path):
        """Vision extraction for Scanned PDFs."""
        images = convert_from_path(pdf_path)
        img = images[0]
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        prompt = """Extract into JSON LIST: [{"customer": "Name", "product_name": "Item", "quantity": 0.0, "uom": "sqm/units", "status": "Status", "document_ref": "ID"}]"""
        
        completion = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}]}],
            temperature=0.0
        )
        return self._parse_json(completion.choices[0].message.content)

    # --- RESTORED LOGIC GATE ---
    def get_departmental_insight(self, context, question, persona):
        """Routes data through professional persona filters."""
        strict_rules = "STRICT: If irrelevant, return 'Invalid Query'. Temp 0.0. No rambling."
        personas = {
            "research": f"{strict_rules} You are a Senior R&D Engineer. Focus on specs and safety.",
            "marketing": f"{strict_rules} You are a Marketing Lead. Focus on USPs.",
            "procurement": f"{strict_rules} You are a BOM Specialist.",
            "finance": f"{strict_rules} You are an Auditor. Focus on ledger accuracy.",
            "content": f"{strict_rules} You are a Content Engine. Merge Specs with Template.",
            "auditor": f"{strict_rules} You are a Mine Ventilation Auditor. Focus on leakage remediation."
        }
        system_msg = personas.get(persona, personas["research"])
        return self._call_llm(system_msg, f"CONTEXT: {context[:12000]}\n\nQUES: {question}", "llama-3.3-70b-versatile")

    def inspect_equipment(self, image_bytes):
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = "Identify equipment, detect corrosion/cracks, provide a rating (1-10) and maintenance steps."
        completion = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
            temperature=0.0
        )
        return completion.choices[0].message.content

    def get_ledger_history(self):
        try:
            return self.supabase.table("universal_ledger").select("*").execute().data
        except: return []

    def query_ledger_history(self, question):
        data = self.get_ledger_history()
        prompt = f"You are the Avux Auditor. Use this history to answer: {json.dumps(data)}"
        return self._call_llm(prompt, question, "llama-3.3-70b-versatile")

    def _call_llm(self, sys, user, model):
        res = self.client.chat.completions.create(messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}], model=model, temperature=0.0)
        content = res.choices[0].message.content
        return self._parse_json(content) if ("[" in content or "{" in content) else content

    def _parse_json(self, content):
        try:
            s = content.find("[") if "[" in content else content.find("{")
            e = (content.rfind("]") + 1) if "]" in content else (content.rfind("}") + 1)
            return json.loads(content[s:e])
        except: return content

    def login(self, e, p): return self.supabase.auth.sign_in_with_password({"email": e, "password": p})
    def update_password(self, p): return self.supabase.auth.update_user({"password": p})