import os
from collections import Counter
from vectorstore_IBM_Mapping import LicenseVectorStore

IBM_FIXED = "ibm_licenses_fixed_ibmmap"  # das ist deine Collection aus dem Log

vs = LicenseVectorStore(
    collection_name=IBM_FIXED,
    embedding_model="BAAI/bge-large-en-v1.5",
    use_adaptive_chunking=False
)

# Chroma "get" kann je nach Version limit/offset brauchen:
data = vs.collection.get(include=["metadatas"], limit=100000)

keys_to_try = ["source", "filename", "file_name", "doc_name", "document", "pdf"]
counts = Counter()

for md in data["metadatas"]:
    if not md:
        continue
    found = None
    for k in keys_to_try:
        if k in md and md[k]:
            found = md[k]
            break
    if found:
        counts[found] += 1
    else:
        counts["<NO_FILENAME_IN_METADATA>"] += 1

for name, c in counts.most_common():
    print(f"{c:5d}  {name}")