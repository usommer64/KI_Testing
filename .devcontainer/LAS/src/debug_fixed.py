#!/usr/bin/env python3
"""
Debug-Script für Fixed Collection
Testet ob Suche funktioniert und zeigt Metadata
"""

import chromadb
from vectorstore_IBM_Mapping import LicenseVectorStore
from collection_names import IBM_FIXED, IBM_ADAPTIVE

# Import specific ChromaDB collection-not-found exception (falls back to ValueError for older versions)
try:
    from chromadb.errors import InvalidCollectionException as _CollectionNotFoundError
except ImportError:
    _CollectionNotFoundError = ValueError

print("=" * 70)
print(f"🔍 DEBUG: {IBM_FIXED} Collection")
print("=" * 70)

# ======================================================================
# TEST 1: Manuelle Suche
# ======================================================================
print("\n" + "=" * 70)
print("TEST 1: MANUELLE SUCHE")
print("=" * 70)

vs = LicenseVectorStore(
    collection_name=IBM_FIXED,
    embedding_model="BAAI/bge-large-en-v1.5"
)

query = "Welche Produkte sind im Produkt WebSphere Application Server als Supporting Product enthalten?"
print(f"\nQuery: {query}\n")

results = vs.search(query, k=5)

print("Top-5 Ergebnisse:")
print("-" * 70)
for i, result in enumerate(results, 1):
    # Alle möglichen Metadata-Keys versuchen
    metadata = result['metadata']
    source = metadata.get('source', 'N/A')
    file_name = metadata.get('file_name', 'N/A')
    page = metadata.get('page', '?')
    word_count = metadata.get('word_count', '?')
    chunk_size = metadata.get('chunk_size', '?')
    
    # Score
    score = result.get('score', result.get('distance', 0.0))
    
    # Text
    text = result['text'][:150].replace('\n', ' ')
    
    print(f"\n{i}. Score: {score:.4f}")
    print(f"   Source: {source}")
    print(f"   File Name: {file_name}")
    print(f"   Page: {page}")
    print(f"   Word Count: {word_count}, Chunk Size: {chunk_size}")
    print(f"   Text: {text}...")


# ======================================================================
# TEST 2: Metadata-Vergleich Adaptive vs Fixed
# ======================================================================
print("\n" + "=" * 70)
print("TEST 2: METADATA-VERGLEICH")
print("=" * 70)

from chromadb.config import Settings

client = chromadb.PersistentClient(
    path='/workspaces/KI_Testing/.devcontainer/LAS/data/chroma_db',
    settings=Settings(anonymized_telemetry=False)
)

adaptive_available = False
try:
    print("\nADAPTIVE Metadata Sample:")
    print("-" * 50)
    coll_a = client.get_collection(IBM_ADAPTIVE)
    sample_a = coll_a.get(limit=2, include=['metadatas', 'documents'])
    for i, meta in enumerate(sample_a['metadatas'], 1):
        print(f"{i}. {meta}")
    adaptive_available = True
except _CollectionNotFoundError:
    print(f"⚠️  ADAPTIVE collection '{IBM_ADAPTIVE}' not found, skipping metadata comparison")

print("\nFIXED Metadata Sample:")
print("-" * 50)
coll_f = client.get_collection(IBM_FIXED)
sample_f = coll_f.get(limit=2, include=['metadatas', 'documents'])
for i, meta in enumerate(sample_f['metadatas'], 1):
    print(f"{i}. {meta}")


# ======================================================================
# TEST 3: Vergleich gleiche Query in beiden Collections
# ======================================================================
print("\n" + "=" * 70)
print("TEST 3: ADAPTIVE vs FIXED VERGLEICH")
print("=" * 70)

if not adaptive_available:
    print(f"⚠️  ADAPTIVE collection '{IBM_ADAPTIVE}' not available, skipping ADAPTIVE vs FIXED comparison")
else:
    vs_adaptive = LicenseVectorStore(collection_name=IBM_ADAPTIVE)
    vs_fixed = LicenseVectorStore(collection_name=IBM_FIXED)

    query = "Was ist Sub-Capacity Lizenzierung?"
    print(f"\nQuery: {query}\n")

    print("ADAPTIVE Top-3:")
    print("-" * 50)
    results_a = vs_adaptive.search(query, k=3)
    for i, r in enumerate(results_a, 1):
        meta = r['metadata']
        source = meta.get('source', meta.get('file_name', 'N/A'))
        score = r.get('score', r.get('distance', 0))
        print(f"{i}. {source[:60]:60} | Score: {score:.4f}")

    print("\nFIXED Top-3:")
    print("-" * 50)
    results_f = vs_fixed.search(query, k=3)
    for i, r in enumerate(results_f, 1):
        meta = r['metadata']
        source = meta.get('source', meta.get('file_name', 'N/A'))
        score = r.get('score', r.get('distance', 0))
        print(f"{i}. {source[:60]:60} | Score: {score:.4f}")


# ======================================================================
# TEST 4: Metadata-Keys Check
# ======================================================================
print("\n" + "=" * 70)
print("TEST 4: WELCHE METADATA-KEYS EXISTIEREN?")
print("=" * 70)

sample_f = coll_f.get(limit=1, include=['metadatas'])
if sample_f['metadatas']:
    meta = sample_f['metadatas'][0]
    print("\nVerfügbare Keys in FIXED:")
    for key in sorted(meta.keys()):
        print(f"  - {key}: {meta[key]}")


print("\n" + "=" * 70)
print("✅ DEBUG ABGESCHLOSSEN")
print("=" * 70)