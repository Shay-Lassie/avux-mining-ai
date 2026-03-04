import os, json, base64, re
from io import BytesIO
from dotenv import load_dotenv
from pypdf import PdfReader
from pdf2image import convert_from_path
from groq import Groq
from supabase import create_client, Client

load_dotenv()

class AvuxProcessor:
    def __init__(self):
        # Initialize Comms
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    # --- INPUT STAGE ---
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
        """Master Ingestor: Switches between Text and Vision automatically."""
        text = self.extract_text_from_pdf(pdf_path)
        
        # Noise Filter for CamScanner
        noise_words = ["camscanner", "scanned with", "pdf scanner"]
        is_only_noise = any(word in text.lower() for word in noise_words) and len(text) < 300
        
        if len(text.strip()) < 100 or is_only_noise:
            return self._extract_via_vision(pdf_path)
        
        # Discovery Phase
        disc_prompt = "Identify: 1. Doc Type (PO/DN), 2. Product, 3. UoM (sqm/units). Return ONLY JSON: {\"type\": \"\", \"product\": \"\", \"uom\": \"\"}"
        profile = self._call_llm(disc_prompt, text[:2000], "llama-3.3-70b-versatile")
        
        if not isinstance(profile, dict): 
            profile = {"type": "Doc", "product": "Item", "uom": "units"}
        
        # Extraction Phase
        ext_prompt = f"""Extract into JSON LIST. Use exact keys: "customer", "product_name", "quantity", "uom", "status", "document_ref".
        Use Product: {profile.get('product')}, UoM: {profile.get('uom')}. Quantity must be numeric."""
        return self._call_llm(ext_prompt, text, "llama-3.3-70b-versatile")

    def _extract_via_vision(self, pdf_path):
        """Vision Transducer for scanned documents."""
        images = convert_from_path(pdf_path)
        img = images[0]
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        prompt = """Extract into JSON LIST. Use keys: "customer", "product_name", "quantity", "uom", "status", "document_ref"."""
        
        res = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
            temperature=0.0
        )
        return self._parse_json(res.choices[0].message.content)

    # --- PROCESSING STAGE ---
    def get_departmental_insight(self, context, question, persona):
        """Routes query through persona-specific logic gates."""
        strict = "STRICT: If irrelevant, return 'Invalid Query'. Tone: Professional Engineer."
        personas = {
            "research": f"{strict} You are a Senior R&D Engineer.",
            "marketing": f"{strict} You are a Marketing Lead.",
            "procurement": f"{strict} You are a BOM Specialist.",
            "finance": f"{strict} You are an Operations Auditor.",
            "content": f"{strict} You are a Content Synthesis Engine.",
            "auditor": f"{strict} You are a Mine Ventilation Auditor."
        }
        sys_msg = personas.get(persona, personas["research"])
        return self._call_llm(sys_msg, f"CONTEXT: {context[:12000]}\n\nQUES: {question}", "llama-3.3-70b-versatile")

    def inspect_equipment(self, image_bytes):
        """Visual Inspection using Vision Transformer logic."""
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = "Identify equipment, detect visual faults (corrosion/cracks), provide rating (1-10) and maintenance steps."
        res = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
            temperature=0.0
        )
        return res.choices[0].message.content

    # --- OUTPUT/DB STAGE ---
    def save_to_ledger(self, data_list):
        try:
            allowed = ["customer", "product_name", "quantity", "uom", "status", "document_ref"]
            clean_payload = []
            for row in data_list:
                clean_row = {k: v for k, v in row.items() if k in allowed}
                try: clean_row['quantity'] = float(str(clean_row.get('quantity', 0)).replace(',', ''))
                except: clean_row['quantity'] = 0.0
                clean_payload.append(clean_row)
            
            self.supabase.table("universal_ledger").insert(clean_payload).execute()
            return "✅ Transmission Successful."
        except Exception as e: return f"❌ Bus Error: {str(e)}"

    def get_ledger_history(self):
        try: return self.supabase.table("universal_ledger").select("*").execute().data
        except: return []

    def query_ledger_history(self, question):
        data = self.get_ledger_history()
        prompt = f"You are the Avux Auditor. Database History: {json.dumps(data)}"
        return self._call_llm(prompt, question, "llama-3.3-70b-versatile")

    # --- HELPERS ---
    def _call_llm(self, sys, user, model):
        res = self.client.chat.completions.create(messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}], model=model, temperature=0.0)
        content = res.choices[0].message.content
        return self._parse_json(content) if ("[" in content or "{" in content) else content

    def _parse_json(self, content):
        try:
            match = re.search(r'(\[.*\]|\{.*\})', content, re.DOTALL)
            return json.loads(match.group(1)) if match else content
        except: return content

    # --- AUTH ---
    def login(self, e, p):
        try:
            return self.supabase.auth.sign_in_with_password({"email": e.strip(), "password": p.strip()})
        except Exception as error:
            return f"AUTH_ERROR: {str(error)}"

    def update_password(self, p):
        try: return self.supabase.auth.update_user({"password": p})
        except Exception as e: return f"Error: {str(e)}"