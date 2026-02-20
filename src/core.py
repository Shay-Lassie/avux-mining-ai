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
        """THE MASTER INGESTOR: Detects Product, Unit, and Document Type."""
        text = self.extract_text_from_pdf(pdf_path)
        
        # 1. THE DISCOVERY PROMPT
        # We ask the AI to identify the "Engineering Profile" of the document
        discovery_prompt = """
        Analyze this industrial document and identify:
        1. Document Type: (Purchase Order or Delivery Note)
        2. Primary Product: (e.g. Vent Seal, Fan, Gas Detector)
        3. Unit of Measure (UoM): (e.g. sqm, units, meters)
        Return ONLY a JSON object: {"type": "", "product": "", "uom": ""}
        """
        
        profile = self._call_llm(discovery_prompt, text[:2000], "llama-3.3-70b-versatile")
        
        # 2. THE EXTRACTION PROMPT (Dynamic)
        # We inject the discovered UoM into the extraction rules
        extract_prompt = f"""
        Extract data from this {profile['type']} for {profile['product']}.
        Format as a JSON LIST of objects:
        [{{
            "customer": "Name",
            "product_name": "{profile['product']}",
            "quantity": 0.0,
            "uom": "{profile['uom']}",
            "status": "Processed",
            "document_ref": "ID Number",
            "document_type": "{profile['type']}"
        }}]
        """
        return self._call_llm(extract_prompt, text, "llama-3.3-70b-versatile")

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
        
    def query_ledger_history(self, user_question):
        """
        DATABASE INQUIRY MODE:
        Queries the Supabase Historian directly using Natural Language.
        """
        # 1. Fetch current data from Supabase (The 'Signal' from the Historian)
        try:
            response = self.supabase.table("operations_ledger").select("*").execute()
            history_data = response.data
        except Exception as e:
            return f"Database Retrieval Fault: {str(e)}"

        # 2. Feed the history to the AI to answer the question
        prompt = f"""
        You are the Avux Operations Auditor. 
        You have access to the Historical Ledger provided in the context.
        TASK: Answer the user's question based ONLY on the database records.
        CONTEXT: {json.dumps(history_data)}
        """
        
        return self._call_llm(prompt, user_question, "llama-3.3-70b-versatile")
    
    def get_ledger_history(self):
        """Fetches all rows from the historian for dashboarding."""
        try:
            response = self.supabase.table("operations_ledger").select("*").execute()
            return response.data
        except Exception as e:
            return None

    def calculate_engineering_logic(self, context, math_problem):
        """
        Calculates complex engineering formulas by forcing the AI 
        to show its 'Workings' and verified math.
        """
        prompt = f"""
        You are an Avux R&D Calculation Agent.
        CONTEXT: {context[:5000]}
        TASK: Solve the user's engineering problem.
        
        STRICT RULES:
        1. State the Formula used (e.g., Atkinson's Law for ventilation).
        2. Identify the Variables from the context or user input.
        3. Perform the calculation step-by-step.
        4. If a value is missing, state 'Insufficient Data to calculate'.
        """
        return self._call_llm(prompt, math_problem, "llama-3.3-70b-versatile")  

    def login(self, email, password):
        """Authenticates the user and sets the session badge."""
        try:
            res = self.supabase.auth.sign_in_with_password({"email": email, "password": password})
            return res
        except Exception as e:
            return f"Auth Error: {str(e)}"

    def get_user(self):
        """Checks who is currently logged in."""
        return self.supabase.auth.get_user()

    def update_password(self, new_password):
        """Allows a logged-in user to update their password without an email link."""
        try:
            res = self.supabase.auth.update_user({"password": new_password})
            return "✅ Password updated successfully."
        except Exception as e:
            return f"❌ Update Failed: {str(e)}"

    def query_ledger_history(self, user_question):
        """
        HISTORIAN INQUIRY:
        Queries the Supabase database and uses LLM to synthesize an answer.
        """
        try:
            # 1. Fetch the 'Historian' data (All rows)
            # This is like pulling the CSV from a PLC log
            response = self.supabase.table("operations_ledger").select("*").execute()
            history_data = response.data
            
            if not history_data:
                return "Historian is empty. No data recorded yet."

            # 2. Feed the data to the LLM as 'Context'
            prompt = f"""
            You are the Avux Operations Auditor.
            You are looking at the 'Avux_Smart_Intranet' ledger history.
            
            TASK: Answer the user's question based ONLY on the provided ledger data.
            LEDGER DATA: {json.dumps(history_data)}
            
            STRICT RULES:
            - Provide totals and summaries clearly.
            - If asking about SQM, sum the 'sqm_delivered' values.
            - If data is missing for a specific date, state it clearly.
            - Tone: Industrial Audit report style.
            """
            
            return self._call_llm(prompt, user_question, "llama-3.3-70b-versatile")
            
        except Exception as e:
            return f"Database Retrieval Fault: {str(e)}"  