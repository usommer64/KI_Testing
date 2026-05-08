"""
Zentrale Konstanten für ChromaDB Collection-Namen.

Importiere diese Konstanten in allen Build-, Debug- und Test-Skripten,
um inkonsistente hard-kodierte Strings zu vermeiden.

Verwendung:
    from collection_names import IBM_FIXED, IBM_ADAPTIVE
"""

# Kanonische Collection für Fixed-Chunking (Baseline)
IBM_FIXED = "ibm_licenses_fixed_ibmmap"

# Kanonische Collection für Adaptive-Chunking (vorerst nicht gebaut)
IBM_ADAPTIVE = "ibm_licenses_adaptive_ibmmap"
