"""
Test what the app is actually querying for
"""

from dotenv import load_dotenv

load_dotenv()

import chromadb
from chromadb.config import Settings
from config import CHROMA_PERSIST_DIRECTORY, CHROMA_TABLE_COLLECTION_NAME

# Simulate what the app does
intent = {
    "measures": ["population"],
    "time": {},
}

# Get collection
client = chromadb.PersistentClient(
    path=CHROMA_PERSIST_DIRECTORY, settings=Settings(anonymized_telemetry=False)
)
collection = client.get_collection(CHROMA_TABLE_COLLECTION_NAME)

print("=" * 60)
print("Testing App's Query Process")
print("=" * 60)

# Test 1: Simple query
print("\n1. Simple Query: 'population'")
results = collection.query(query_texts=["population"], n_results=5)
print(f"   Results: {len(results['metadatas'][0])}")
if results["metadatas"][0]:
    for i, metadata in enumerate(results["metadatas"][0][:3]):
        print(f"   {i + 1}. {metadata.get('table_code')}: {metadata.get('table_name')}")

# Test 2: What the app might be building
from src.utils.text_utils import build_retrieval_query

query_string = build_retrieval_query(intent, {})
print(f"\n2. App's Built Query: '{query_string}'")
results2 = collection.query(query_texts=[query_string], n_results=5)
print(f"   Results: {len(results2['metadatas'][0])}")
if results2["metadatas"][0]:
    for i, metadata in enumerate(results2["metadatas"][0][:3]):
        print(f"   {i + 1}. {metadata.get('table_code')}: {metadata.get('table_name')}")
else:
    print("   [ERROR] No results for app's query!")

print("\n" + "=" * 60)
