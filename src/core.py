import os, json, base64
from io import BytesIO
from dotenv import load_dotenv
from pypdf import PdfReader
from pdf2image import convert_from_path
from groq import Groq
from supabase import create_client, Client

load_dotenv()

class AvuxProcessor:
    """AVUX CORE PROCESSOR: The Central Control Unit for Industrial Intelligence."""
    
    def __init__(self):
        # Initialize Power & Comms
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    def extract_text_from_pdf(self, pdf_path):
        """Standard Text Scraper (Digital Signal)"""
        text = ""
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                content = page.extract_text()
                if content: text += content
        except: pass
        return text

    def ingest_document(self, pdf_path):
        """THE MASTER INGESTOR: Auto-detects signal quality and extracts via Universal Schema."""
        text = self.extract_text_from_pdf(pdf_path)
        
        # Threshold Gate: If scan detected or text is noise (CamScanner), use Vision
        noise_words = ["camscanner", "scanned with", "pdf scanner"]
        is_only_noise = any(word in text.lower() for word in noise_words) and len(text) < 300
        
        if len(text.strip()) < 100 or is_only_noise:
            return self._extract_via_vision(pdf_path)
        
        # Discovery Phase
        discovery_prompt = "Identify: 1. Doc Type (PO/DN), 2. Product, 3. UoM (sqm/units). Return ONLY JSON: {\"type\": \"\", \"product\": \"\", \"uom\": \"\"}"
        profile = self._call_llm(discovery_prompt, text[:2000], "llama-3.3-70b-versatile")
        if not isinstance(profile, dict): profile = {"type": "Doc", "product": "Item", "uom": "units"}
        
        # Universal Extraction
        extract_prompt = f"""
        Extract into JSON LIST. USE THESE KEYS: "customer", "product_name", "quantity", "uom", "status", "document_ref"
        Product name: {profile.get('product')}, UoM: {profile.get('uom')}.
        STRICT: quantity must be a number only.
        """
        return self._call_llm(extract_prompt, text, "llama-3.3-70b-versatile")

    def _extract_via_vision(self, pdf_path):
        """Vision extraction for Scanned PDFs using Llama-Scout."""
        images = convert_from_path(pdf_path)
        img = images[0]
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        prompt = """Extract delivery data into JSON LIST. Use keys: "customer", "product_name", "quantity", "uom", "status", "document_ref"."""
        
        completion = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
            temperature=0.0
        )
        return self._parse_json(completion.choices[0].message.content)

    def inspect_equipment(self, image_bytes):
        """VISUAL INSPECTOR: Detects physical faults on site equipment."""
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = "Identify equipment, detect visual faults (corrosion/cracks), provide a rating (1-10) and maintenance steps."
        completion = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
            temperature=0.0
        )
        return completion.choices[0].message.content

    def get_departmental_insight(self, context, question, persona):
        """Persona Routing Logic."""
        strict_rules = "STRICT: If irrelevant, return 'Invalid Query'. Temp 0.0. No rambling."
        personas = {
            "research": f"{strict_rules} You are a Senior R&D Engineer. Focus on technical specs.",
            "marketing": f"{strict_rules} You are a Marketing Lead. Focus on benefits.",
            "content": f"{strict_rules} You are a Content Engine. Merge Specs with Template.",
            "auditor": f"{strict_rules} You are a Mine Ventilation Auditor."
        }
        system_msg = personas.get(persona, personas["research"])
        return self._call_llm(system_msg, f"CONTEXT: {context[:12000]}\n\nQUES: {question}", "llama-3.3-70b-versatile")

    def save_to_ledger(self, data_list):
        """Strict schema enforcement and data transmission to Supabase."""
        try:
            allowed_keys = ["customer", "product_name", "quantity", "uom", "status", "document_ref"]
            cleaned_payload = []
            for row in data_list:
                clean_row = {k: v for k, v in row.items() if k in allowed_keys}
                try: clean_row['quantity'] = float(clean_row.get('quantity', 0))
                except: clean_row['quantity'] = 0.0
                cleaned_payload.append(clean_row)
            
            self.supabase.table("universal_ledger").insert(cleaned_payload).execute()
            return "✅ Transmission Successful."
        except Exception as e: return f"❌ Bus Error: {str(e)}"

    def get_ledger_history(self):
        """Fetches history for the analytics dashboard."""
        try: return self.supabase.table("universal_ledger").select("*").execute().data
        except: return []

    def query_ledger_history(self, question):
        """Natural Language querying of the database historian."""
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