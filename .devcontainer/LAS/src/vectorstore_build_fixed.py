"""
Build-Script für FIXED Chunk-Size Experiment (400/100)
"""

from pathlib import Path
import logging
from vectorstore import LicenseVectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 70)
    logger.info("🏗️  BAUE VECTORSTORE MIT FESTER CHUNK-SIZE: 400/100")
    logger.info("=" * 70)
    
    data_dir = Path(__file__).parent.parent / "data"
    
    # Vectorstore mit FIXED Chunking
    vectorstore = LicenseVectorStore(
        collection_name="ibm_licenses_fixed",  # ← Anderer Name!
        embedding_model="BAAI/bge-large-en-v1.5",
        use_adaptive_chunking=False  # ← FIXED MODE!
    )
    
    # Dokumente laden
    documents = vectorstore.load_and_process_documents(data_dir)
    logger.info(f"✅ Gesamt: {len(documents)} Chunks")
    
    # Hinzufügen
    vectorstore.add_documents(documents)
    
    # Stats
    stats = vectorstore.get_stats()
    logger.info("=" * 70)
    logger.info("📊 FERTIG")
    logger.info("=" * 70)
    logger.info(f"Collection:  {stats['collection_name']}")
    logger.info(f"Dokumente:   {stats['total_documents']:,}")
    logger.info(f"Adaptive:    {stats['adaptive_chunking']}")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()