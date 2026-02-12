import os
from dotenv import load_dotenv
from pypdf import PdfReader
from groq import Groq

load_dotenv()

class AvuxProcessor:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
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
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"CONTEXT:\n{product_data[:15000]}\n\nQUESTION: {question}"}
                ],
                model="llama-3.3-70b-versatile", 
                temperature=0.0,
                top_p=0.1,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Model Error: {str(e)}"