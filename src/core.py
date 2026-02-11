import os
from dotenv import load_dotenv
from pypdf import PdfReader
from groq import Groq

# Load the secret API Key
load_dotenv()

class AvuxProcessor:
    def __init__(self):
        # Initialize the 'Processor' (Groq)
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
    def extract_text_from_pdf(self, pdf_path):
        """Converts the Analog PDF into Digital Text for the LLM."""
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
        """Logic Gate: Routes the data through different professional lenses."""
        
        # STRICT RULES BASE PROMPT - Applied to all personas
        strict_rules = """STRICT RULES:
1. You MUST follow all instructions exactly as given without deviation.
2. Focus ONLY on the specific persona's perspective and expertise.
3. If a format is requested (e.g., table, list, bullet points), you MUST use that exact format.
4. Do NOT add extra explanations, commentary, or disclaimers unless explicitly requested.
5. If you cannot find specific information in the provided context, state "Information not found in document" for that specific item.
6. Be precise and concise - no filler text.
7. Temperature is set to 0.0 - responses must be deterministic and consistent."""

        # System Prompts = The 'Firmware' of the AI
        personas = {
            "rd": f"""{strict_rules}
            
            You are a Senior R&D Engineer analyzing technical specifications.
            FOCUS: Technical specifications, safety factors, engineering tolerances, material properties.
            RESPONSE STYLE: Technical, precise, data-driven.
            FORMAT: Clear technical documentation style.""",
            
            "marketing": f"""{strict_rules}
            
            You are a Marketing Manager analyzing product benefits.
            FOCUS: Customer benefits, unique selling points, market advantages, application scenarios.
            RESPONSE STYLE: Persuasive, benefit-oriented, customer-focused.
            FORMAT: Clear bullet points highlighting benefits.""",
            
            "procurement": f"""{strict_rules}
            
            You are a Procurement & BOM Specialist.
            STRICT MATERIAL RULES:
            1. ONLY extract materials SPECIFICALLY related to the CUSTOM VENT SEAL assembly.
            2. IGNORE completely: General factory supplies, workshop equipment, overhead items, or non-specific materials.
            3. QUANTITY REQUIREMENT: If a quantity is mentioned (e.g., '2 rolls', '5kg', 'per unit', 'required for production'), you MUST include it.
            4. SPECIFICATION REQUIREMENT: Include ALL technical specifications mentioned (material type, grade, thickness, dimensions, etc.).
            5. FORMAT: You MUST use this exact table format:
               | Material | Specification | Quantity | Notes |
               |----------|---------------|----------|-------|
            6. If quantity is not explicitly stated: Mark as 'TBD - Refer to Drawing'
            7. If specification is incomplete: Mark as 'See document section X' (if location is mentioned)
            8. Do NOT invent or assume any materials not explicitly mentioned.""",

            "estimation": f"""{strict_rules}
            You are an R&D Estimation Engineer. 
            TASK: Calculate the required materials for a Custom Vent Seal installation.
            LOGIC:
            1. If the user provides Gallery Dimensions (Height x Width), calculate the surface area.
            2. Estimate material based on area + 15% wastage factor.
            3. Format the output as an 'Engineering Estimate' with a disclaimer that final drawings are required."""
        }

        system_message = personas.get(persona, personas["rd"])

        try:
            # Note: We use llama-3.3-70b-versatile. 
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": f"{system_message}\n\nCONTEXT DATA (First 12,000 chars): {product_data[:12000]}"
                    },
                    {
                        "role": "user",
                        "content": question,
                    }
                ],
                model="llama-3.3-70b-versatile", 
                temperature=0.0,  # CHANGED: Set to 0.0 for deterministic, consistent output
                max_tokens=2000,   # Added for consistent response length
                top_p=0.1,         # Added for more focused responses
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Model Error: {str(e)}. Try updating model ID in core.py."

# --- Testing the Circuit ---
if __name__ == "__main__":
    # Initialize Avux
    avux = AvuxProcessor()
    
    # Update this to your actual PDF filename
    PDF_PATH = "data/vent_seal_spec.pdf" 
    
    if os.path.exists(PDF_PATH):
        print(f"--- Avux Initialized: Loading {PDF_PATH} ---")
        print(f"--- Temperature set to: 0.0 (Deterministic Mode) ---")
        raw_signal = avux.extract_text_from_pdf(PDF_PATH)

        #estimation question
        user_query = "The client hauling is 3.5m high and 8m wide. Estimate the PVC material required for one seal."

        response = avux.get_departmental_insight(raw_signal, user_query, "estimation")
        print(response)

        # rd question
        user_query = "What materials are required to produce this seal?"
        
        # Test Case: Procurement/Manufacturing Perspective
        print(f"\n[QUERY]: {user_query}")
        print("\n[AVUX PROCUREMENT RESPONSE]:")
        response = avux.get_departmental_insight(raw_signal, user_query, "procurement")
        print(response)
        
        # Optional: Test other personas
        print("\n" + "="*60)
        print("[TESTING OTHER PERSONAS WITH TEMPERATURE=0.0]")
        print("="*60)
        
        test_questions = [
            "What are the technical specifications and safety factors?",
            "What are the key customer benefits and selling points?"
        ]
        
        test_personas = ["rd", "marketing"]
        
        for i, (question, persona) in enumerate(zip(test_questions, test_personas)):
            print(f"\n[{persona.upper()} TEST {i+1}]: {question}")
            print(f"[RESPONSE]:")
            response = avux.get_departmental_insight(raw_signal[:5000], question, persona)
            print(response[:500] + "..." if len(response) > 500 else response)
            print("-" * 40)
            
    else:
        print(f"Error: No PDF found at {PDF_PATH}. Ensure the file is in the root folder.")