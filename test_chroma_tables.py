"""
Quick diagnostic: Check if table-level ChromaDB index exists and has data
"""

import chromadb
from chromadb.config import Settings
from config import CHROMA_PERSIST_DIRECTORY, CHROMA_TABLE_COLLECTION_NAME

print("=" * 60)
print("DIAGNOSTIC: Checking Table-Level ChromaDB Index")
print("=" * 60)

# Connect to ChromaDB
client = chromadb.PersistentClient(
    path=CHROMA_PERSIST_DIRECTORY, settings=Settings(anonymized_telemetry=False)
)

# Try to get table collection
print(f"\n1. Looking for collection: {CHROMA_TABLE_COLLECTION_NAME}")
try:
    collection = client.get_collection(CHROMA_TABLE_COLLECTION_NAME)
    print("   [OK] Collection found!")

    # Get first few items to check if populated
    print("\n2. Checking if collection has data...")
    sample = collection.get(limit=5)

    if sample["ids"]:
        print("   [OK] Collection has data! Sample IDs:")
        for i, id_val in enumerate(sample["ids"][:5]):
            print(f"      {i + 1}. {id_val}")

        # Test a query
        print("\n3. Testing Query: 'population'")
        results = collection.query(query_texts=["population"], n_results=3)

        if results["metadatas"] and results["metadatas"][0]:
            print(f"   [OK] Query works! Found {len(results['metadatas'][0])} results")
            print("\n   Top 3 results:")
            for i, metadata in enumerate(results["metadatas"][0]):
                table_code = metadata.get("table_code", "N/A")
                table_name = metadata.get("table_name", "N/A")
                distance = results["distances"][0][i]
                score = 1.0 - distance
                print(f"   {i + 1}. {table_code}: {table_name}")
                print(f"      Distance: {distance:.3f}, Score: {score:.3f}")
        else:
            print("   [ERROR] Query returned no results!")
            print("   Problem: Collection has data but query doesn't match")

    else:
        print("   [ERROR] Collection is EMPTY!")
        print("   ACTION NEEDED: Run 'python index/buil_index_table.py'")

except Exception:
    print("   [ERROR] Collection NOT FOUND")
    print("   ACTION NEEDED: Run 'python index/buil_index_table.py'")

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)
