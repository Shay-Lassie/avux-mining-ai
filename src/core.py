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
    
    def ingest_document(self, pdf_path):
        """
        AUTO-RANGING INGESTOR:
        Detects if signal is Digital (Text) or Analog (Scan) and processes accordingly.
        """
        text = ""
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                content = page.extract_text()
                if content: text += content
        except Exception:
            pass

        # Threshold Gate: If less than 50 chars, switch to Vision Transducer
        if len(text.strip()) < 50:
            return self._extract_via_vision(pdf_path)
        else:
            return self._extract_via_text(text)

    def _extract_via_text(self, text):
        """Standard extraction for Digital PDFs."""
        prompt = "Extract delivery data into a JSON LIST: [{'customer': 'Name', 'seal_type': 'Type', 'status': 'Status', 'sqm_delivered': 0.0, 'delivery_note': 'ID'}]"
        return self._call_llm(prompt, text, model="llama-3.3-70b-versatile")

    def _extract_via_vision(self, pdf_path):
        """Vision extraction for Scanned PDFs using Llama-3.2-Vision replacement: meta llama."""
        # Convert PDF to Image (Requires Poppler)
        images = convert_from_path(pdf_path)
        img = images[0]
        
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        prompt = "Extract delivery data from this scan into a JSON LIST: customer, seal_type, status, sqm_delivered, delivery_note."
        
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
        """Logic Gate: Routes data through professional persona filters."""
        
        strict_rules = "STRICT: If query is irrelevant, return 'Invalid Query'. Temp 0.0. No rambling."

        personas = {
            "research": f"{strict_rules} You are a Senior R&D Engineer. Focus on material science and tolerances.",
            "marketing": f"{strict_rules} You are a Marketing Lead. Focus on USPs and customer benefits.",
            "procurement": f"{strict_rules} You are a BOM Specialist. Focus on materials and quantities.",
            "finance": f"{strict_rules} You are an Auditor. Focus on sqm counts and delivery tracking.",
            "content": f"{strict_rules} You are a Content Engine. Merge Technical Signal with Reference Template."
        }

        system_msg = personas.get(persona, personas["research"])

        return self._call_llm(system_msg, f"CONTEXT: {context[:12000]}\n\nQUES: {question}", "llama-3.3-70b-versatile")

    # --- OUTPUT STAGE: Database & Helpers ---

    def _call_llm(self, system_prompt, user_content, model):
        completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model=model,
            temperature=0.0
        )
        # Check if we expect JSON (for ingestion) or text (for chat)
        content = completion.choices[0].message.content
        if "[" in content and "]" in content:
            return self._parse_json(content)
        return content

    def _parse_json(self, content):
        try:
            start = content.find("[")
            end = content.rfind("]") + 1
            return json.loads(content[start:end])
        except:
            return f"Error Parsing JSON: {content}"

    def save_to_ledger(self, data_list):
        """Writes verified records to Avux_Smart_Intranet DB."""
        try:
            self.supabase.table("operations_ledger").insert(data_list).execute()
            return "✅ Transmission Successful: Data logged to Supabase."
        except Exception as e:
            return f"❌ Bus Error: {str(e)}"