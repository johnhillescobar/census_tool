import chromadb

client = chromadb.PersistentClient(path="chroma")
collection = client.get_collection("census_vars")

print("Testing population search...")
results = collection.query(
    query_texts=["population people residents inhabitants"],
    n_results=5,
    include=["documents", "metadatas", "distances"],
)

print("Population search results:")
for i, (doc, meta, dist) in enumerate(
    zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
):
    print(f"{i + 1}. Distance: {dist:.3f}")
    print(f"   Variable: {meta['var']}")
    print(f"   Label: {meta['label'][:100]}...")
    print(f"   Concept: {meta['concept'][:100]}...")
    print()

print("\nTesting total population search...")
results2 = collection.query(
    query_texts=["total population B01003"],
    n_results=3,
    include=["documents", "metadatas", "distances"],
)

print("Total population search results:")
for i, (doc, meta, dist) in enumerate(
    zip(results2["documents"][0], results2["metadatas"][0], results2["distances"][0])
):
    print(f"{i + 1}. Distance: {dist:.3f}")
    print(f"   Variable: {meta['var']}")
    print(f"   Label: {meta['label']}")
    print(f"   Concept: {meta['concept']}")
    print()
