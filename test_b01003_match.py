"""
Test why B01003 isn't ranking high for 'population' query
"""

import chromadb
from chromadb.config import Settings
from config import CHROMA_PERSIST_DIRECTORY, CHROMA_TABLE_COLLECTION_NAME

client = chromadb.PersistentClient(
    path=CHROMA_PERSIST_DIRECTORY, settings=Settings(anonymized_telemetry=False)
)

collection = client.get_collection(CHROMA_TABLE_COLLECTION_NAME)

print("=" * 70)
print("Testing: Why doesn't 'population' query match B01003?")
print("=" * 70)

# Query for 'population' and get MORE results
print("\n1. Querying for 'population' (top 10 results):")
results = collection.query(query_texts=["population"], n_results=10)

print(f"\nFound {len(results['metadatas'][0])} results:\n")
for i, (metadata, distance) in enumerate(
    zip(results["metadatas"][0], results["distances"][0])
):
    table_code = metadata.get("table_code")
    table_name = metadata.get("table_name")[:50]  # Truncate long names
    score = 1.0 - distance
    marker = " <-- THIS IS IT!" if table_code == "B01003" else ""
    print(f"{i + 1:2}. {table_code:8} Score: {score:.3f}  {table_name}{marker}")

# Also try "total population"
print("\n" + "=" * 70)
print("2. Querying for 'total population' (top 10 results):")
results2 = collection.query(query_texts=["total population"], n_results=10)

print(f"\nFound {len(results2['metadatas'][0])} results:\n")
for i, (metadata, distance) in enumerate(
    zip(results2["metadatas"][0], results2["distances"][0])
):
    table_code = metadata.get("table_code")
    table_name = metadata.get("table_name")[:50]  # Truncate
    score = 1.0 - distance
    marker = " <-- THIS IS IT!" if table_code == "B01003" else ""
    print(f"{i + 1:2}. {table_code:8} Score: {score:.3f}  {table_name}{marker}")

print("\n" + "=" * 70)
