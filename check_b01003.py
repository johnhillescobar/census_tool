"""
Check if B01003 (Total Population) is in the index
"""

import chromadb
from chromadb.config import Settings
from config import CHROMA_PERSIST_DIRECTORY, CHROMA_TABLE_COLLECTION_NAME

print("=" * 60)
print("Checking for B01003 (Total Population) in index")
print("=" * 60)

client = chromadb.PersistentClient(
    path=CHROMA_PERSIST_DIRECTORY, settings=Settings(anonymized_telemetry=False)
)

collection = client.get_collection(CHROMA_TABLE_COLLECTION_NAME)

# Search for B01003 specifically
print("\n1. Looking for table code 'B01003'...")
results = collection.get(ids=["B01003"], include=["metadatas", "documents"])

if results["ids"]:
    print("[OK] B01003 FOUND in index!")
    metadata = results["metadatas"][0]
    document = results["documents"][0]
    print(f"\nMetadata:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")
    print(f"\nDocument text:")
    print(f"  {document}")
else:
    print("[ERROR] B01003 NOT FOUND in index!")
    print("This table should be there for population queries.")

# Check what datasets are in the index
print("\n" + "=" * 60)
print("2. Checking which datasets are in the index...")
print("=" * 60)

sample = collection.get(limit=20, include=["metadatas"])
datasets = set()
for metadata in sample["metadatas"]:
    datasets.add(metadata.get("dataset", "unknown"))

print(f"\nDatasets found (from sample of 20 tables):")
for ds in sorted(datasets):
    print(f"  - {ds}")

print("\n" + "=" * 60)
