import os
from dotenv import load_dotenv
from pypdf import PdfReader
from groq import Groq
from supabase import create_client, Client
import json

load_dotenv()

class AvuxProcessor:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        # Initialize Supabase Client
        url: str = os.getenv("https://mjhupvgxancirpudumzl.supabase.co/operations_ledger")
        key: str = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlpbmVwc2xvanp4YWh3cnRiamp2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA2NDA0NzIsImV4cCI6MjA4NjIxNjQ3Mn0.OQpCLBGXCGTlthRiZkfFMvqmTFouGlfe8kZREBya-t0")
        self.supabase: Client = create_client(url, key)

     # New Function to extract structured data specifically for the database
    def extract_structured_data(self, product_data):
        """Uses the AI to convert raw PDF text into a JSON object for the DB."""
        prompt = """
        Analyze the following delivery log and extract data into a JSON LIST. 
        Format: [{"customer": "Name", "seal_type": "Type", "sqm_delivered": 00.0, "status": "Delivered", "delivery_note": "ID"}]
        STRICT: Only return the JSON list. No text. If data missing, use null.
        """

    def extract_text_from_pdf(self, pdf_path):
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                content = page.extract_text()
                if content:
                    text += content
            return text
        except Exception as e:
            return f"Signal Error: {str(e)}"

    def get_departmental_insight(self, product_data, question, persona):
        # STRENGTHENED STRICT RULES: Added a 'Relevance Gate'
        strict_rules = """STRICT RULES:
        1. Focus ONLY on the specific persona's expertise.
        2. If the user question is nonsensical, irrelevant, or lacks engineering logic, respond ONLY with: 'Invalid Query: Please provide a specific technical or operational question.'
        3. Do NOT provide a general summary of the document unless explicitly asked for one.
        4. If the answer is not in the text, state: 'Information not found in document.'
        5. No filler text, no 'Here is your information', no polite transitions.
        6. Temperature is 0.0 - be deterministic."""

        personas = {
            "research": f"""{strict_rules}
            You are a Senior Research & Development Engineer. 
            FOCUS: Engineering specs, material science, and safety tolerances. 
            RESPONSE STYLE: Data-points only. Be extremely concise. If asked a vague question, do not describe the product; ask for clarification.""",
            
            "marketing": f"""{strict_rules}
            You are a Product Marketing Manager. Focus on USP and benefits.""",
            
            "procurement": f"""{strict_rules}
            You are a Procurement Specialist. Focus on BOM, quantities, and materials. Use tables.""",
            
            "finance": f"""{strict_rules}
            You are an Operations Auditor. Track deliveries, sqm counts, and sign-offs from the provided logs.""",
            
            "content": f"""{strict_rules}
            You are a Content Synthesis Engine. Merge the technical 'Signal' with the reference 'Structure' to create professional documents."""
        }

        system_message = personas.get(persona, personas["research"])

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": product_data[:10000]}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.0
            )
            # Parse the string into a real Python list
            return json.loads(chat_completion.choices[0].message.content)
        except Exception as e:
            return f"Parsing Error: {str(e)}"
        
    # New Function to SAVE to database
    def save_to_ledger(self, data_list):
        """Inserts the JSON list into the Supabase table."""
        try:
            response = self.supabase.table("operations_ledger").insert(data_list).execute()
            return "Success: Data logged to Operational Ledger."
        except Exception as e:
            return f"Database Error: {str(e)}"

    # New Function to READ from database
    def get_ledger_history(self):
        """Retrieves history from Supabase."""
        response = self.supabase.table("operations_ledger").select("*").execute()
        return response.data