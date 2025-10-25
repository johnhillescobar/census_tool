"""
Test if .env file loads correctly
"""

from dotenv import load_dotenv
import os

print("=" * 60)
print("Testing .env File Loading")
print("=" * 60)

# Load .env
load_dotenv()

# Check keys
keys_to_check = ["OPENAI_API_KEY", "CHROMA_OPENAI_API_KEY", "LANGCHAIN_API_KEY"]

for key in keys_to_check:
    value = os.getenv(key)
    if value:
        # Show first 10 and last 10 characters
        masked = f"{value[:10]}...{value[-10:]}" if len(value) > 20 else value
        print(f"[OK] {key}: {masked}")
    else:
        print(f"[MISSING] {key}: Not set!")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
