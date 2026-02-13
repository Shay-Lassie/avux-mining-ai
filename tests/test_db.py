import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

try:
    supabase = create_client(url, key)
    # Try to fetch just one row from any table to test the connection
    response = supabase.table("operations_ledger").select("*").limit(1).execute()
    print("✅ Connection Successful! The URL and Key are correct.")
except Exception as e:
    print(f"❌ Connection Failed: {e}")