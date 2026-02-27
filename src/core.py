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
        
        discovery_prompt = "Identify: 1. Doc Type (PO/DN), 2. Product, 3. UoM (sqm/units). Return JSON: {\"type\": \"\", \"product\": \"\", \"uom\": \"\"}"
        profile = self._call_llm(discovery_prompt, text[:2000], "llama-3.3-70b-versatile")
        if not isinstance(profile, dict): profile = {"type": "Doc", "product": "Item", "uom": "units"}
        
        extract_prompt = f"Extract into JSON LIST: [{{'customer': 'Name', 'product_name': '{profile.get('product')}', 'quantity': 0.0, 'uom': '{profile.get('uom')}', 'status': 'Processed', 'document_ref': 'ID'}}]"
        return self._call_llm(extract_prompt, text, "llama-3.3-70b-versatile")

    def _extract_via_vision(self, pdf_path):
        images = convert_from_path(pdf_path)
        img = images[0]
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        prompt = "Extract into JSON LIST: [{'customer': 'Name', 'product_name': 'Item', 'quantity': 0.0, 'uom': 'sqm/units', 'status': 'Status', 'document_ref': 'ID'}]"
        completion = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
            temperature=0.0
        )
        return self._parse_json(completion.choices[0].message.content)

    def inspect_equipment(self, image_bytes):
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = "Identify equipment in this photo, detect visual faults (corrosion/cracks), and provide a condition rating (1-10) with maintenance steps."
        completion = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
            temperature=0.0
        )
        return completion.choices[0].message.content

    def save_to_ledger(self, data_list):
        """Writes verified records to the UNIVERSAL_LEDGER DB."""
        try:
            # Pointing specifically to the universal table
            res = self.supabase.table("universal_ledger").insert(data_list).execute()
            return "✅ Transmission Successful."
        except Exception as e:
            # This will tell us EXACTLY what is wrong (e.g., "column quantity does not exist")
            return f"❌ Bus Error: {str(e)}"

    def get_ledger_history(self):
        return self.supabase.table("universal_ledger").select("*").execute().data

    def query_ledger_history(self, question):
        data = self.get_ledger_history()
        prompt = f"You are the Avux Auditor. Use this history: {json.dumps(data)}"
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