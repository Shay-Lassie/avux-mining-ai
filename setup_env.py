# setup_env.py
import subprocess
import sys

def check_and_install():
    required_packages = [
        "groq", "pypdf", "python-dotenv", "supabase", "pdf2image", "streamlit", "pandas"
    ]
    
    print("--- Avux System Health Check ---")
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} is installed.")
        except ImportError:
            print(f"⚠️ {package} missing. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

    print("\n--- Checking for System Dependencies (Mac) ---")
    # Checking for Poppler (needed for PDF-to-Image)
    try:
        result = subprocess.run(["pdftoppm", "-v"], capture_output=True)
        print("✅ Poppler/pdftoppm detected.")
    except FileNotFoundError:
        print("❌ Poppler is missing! Run 'brew install poppler' in your terminal.")

if __name__ == "__main__":
    check_and_install()