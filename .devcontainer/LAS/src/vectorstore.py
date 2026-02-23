#!/usr/bin/env python3
"""
Vectorstore für Lizenzierungsdokumente
Verwendet ChromaDB + BGE-Large-en-v1.5 Embeddings
Unterstützt: PDF + DOCX mit adaptiver Chunk-Size
"""

from pathlib import Path
from typing import List, Optional
import logging

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from langchain.schema import Document

from loader import LicenseDocumentLoader

# ===== PANDAS FÜR CSV =====
import pandas as pd

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== PFAD ZUR STATISTIK-CSV =====
STATS_CSV = Path(__file__).parent.parent / "data" / "document_stats.csv"


# ===== ADAPTIVE CHUNK-SIZE FUNKTION =====
def get_chunk_size_by_words(word_count):
    """
    Adaptive Chunk-Size basierend auf Wort-Count.
    Optimiert für Lizenzdokumente (577-10077 Wörter).
    """
    if word_count < 1000:
        return 500, 125
    elif word_count < 2000:
        return 450, 110
    elif word_count < 3500:
        return 400, 100
    elif word_count < 5000:
        return 350, 90
    elif word_count < 7000:
        return 300, 75
    else:
        return 250, 60


class LicenseVectorStore:
    """
    Vektordatenbank für Lizenzdokumente.
    
    Features:
    - BGE-Large-en-v1.5 Embeddings (Top-Qualität)
    - ChromaDB (persistent, lokal)
    - Asymmetrische Suche (Query-Prefix)
    - Adaptive Chunk-Size basierend auf Dokumentlänge
    - Multi-Format: PDF + DOCX
    """
    
    def __init__(
        self,
        collection_name: str = "ibm_licenses",
        persist_directory: str = None,
        embedding_model: str = "BAAI/bge-large-en-v1.5"
    ):
        """
        Args:
            collection_name: Name der ChromaDB Collection
            persist_directory: Pfad für persistente Speicherung
            embedding_model: Hugging Face Model-Name
        """
        self.collection_name = collection_name
        
        # Default: Speichern neben src/
        if persist_directory is None:
            persist_directory = str(Path(__file__).parent.parent / "data" / "chroma_db")
        
        self.persist_directory = persist_directory
        
        # Embedding-Modell laden
        logger.info(f"📥 Lade Embedding-Modell: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        logger.info(f"✅ Modell geladen: {self.embedding_model.get_sentence_embedding_dimension()} Dimensionen")
        
        # DOKUMENT-STATISTIKEN LADEN
        if STATS_CSV.exists():
            self.doc_stats = pd.read_csv(STATS_CSV).set_index('filename')
            logger.info(f"✅ Dokument-Statistiken geladen: {len(self.doc_stats)} Docs")
        else:
            logger.warning(f"⚠️ Keine Statistiken gefunden: {STATS_CSV}")
            logger.warning("   Führe 'python analyze_documents.py' aus!")
            self.doc_stats = None
        
        # ChromaDB Client erstellen
        logger.info(f"📂 Initialisiere ChromaDB in: {persist_directory}")
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        # Collection erstellen oder laden
        try:
            self.collection = self.client.get_collection(name=collection_name)
            logger.info(f"✅ Collection '{collection_name}' geladen ({self.collection.count()} Dokumente)")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "Licensing Documents (PDF + DOCX)"}
            )
            logger.info(f"✅ Collection '{collection_name}' erstellt")
    
    def embed_texts(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        """
        Erstellt Embeddings für Texte.
        
        Args:
            texts: Liste von Texten
            is_query: True für Queries (nutzt Query-Prefix)
            
        Returns:
            Liste von Embedding-Vektoren
        """
        if is_query:
            # Query-Prefix für bessere Retrieval-Qualität
            texts = [
                f"Represent this sentence for searching relevant passages: {text}"
                for text in texts
            ]
        
        # Embeddings erstellen
        embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        return embeddings.tolist()
    
    def add_documents(self, documents: List[Document]) -> None:
        """
        Fügt Dokumente zur Vektordatenbank hinzu.
        
        Args:
            documents: Liste von LangChain Documents
        """
        if not documents:
            logger.warning("Keine Dokumente zum Hinzufügen")
            return
        
        logger.info(f"📄 Füge {len(documents)} Dokumente hinzu...")
        
        # Texte und Metadaten extrahieren
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        
        # IDs generieren
        ids = [f"doc_{i}" for i in range(len(documents))]
        
        # Embeddings erstellen
        embeddings = self.embed_texts(texts, is_query=False)
        
        # Zu ChromaDB hinzufügen
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        logger.info(f"✅ {len(documents)} Dokumente hinzugefügt")
    
    def search(self, query: str, k: int = 5) -> List[dict]:
        """
        Sucht ähnliche Dokumente.
        
        Args:
            query: Suchquery
            k: Anzahl Ergebnisse
            
        Returns:
            Liste von Dictionaries mit Ergebnissen
        """
        logger.info(f"🔍 Suche: '{query}'")
        
        # Query-Embedding erstellen
        query_embedding = self.embed_texts([query], is_query=True)[0]
        
        # Suche durchführen
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
        
        # Ergebnisse formatieren
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'id': results['ids'][0][i],
                'text': results['documents'][0][i],  # ← GEÄNDERT: 'text' statt 'document'
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i]  # ← GEÄNDERT: 'distance' statt 'score'
            })
        
        logger.info(f"✅ {len(formatted_results)} Ergebnisse gefunden")
        return formatted_results
    
    def get_stats(self) -> dict:
        """
        Gibt Statistiken über die Collection zurück.
        """
        count = self.collection.count()
        return {
            'collection_name': self.collection_name,
            'total_documents': count,
            'persist_directory': self.persist_directory
        }


# ===== BUILD-FUNKTION MIT ADAPTIVER CHUNK-SIZE + DOCX =====
def build_vectorstore(
    data_dir: str = None,
    chunk_size: int = None,
    chunk_overlap: int = None
) -> LicenseVectorStore:
    """
    Baut die Vektordatenbank NEU auf mit adaptiver Chunk-Size.
    Unterstützt PDF + DOCX.
    """
    if data_dir is None:
        data_dir = str(Path(__file__).parent.parent / "data")

    logger.info("="*70)
    logger.info("🏗️  BAUE VECTORSTORE MIT ADAPTIVER CHUNK-SIZE + DOCX-SUPPORT")
    logger.info("="*70)

    # Vectorstore initialisieren
    vs = LicenseVectorStore()

    # Sammle alle Dateien
    pdf_files = list(Path(data_dir).glob("*.pdf"))
    docx_files = list(Path(data_dir).glob("*.docx"))
    
    total_files = len(pdf_files) + len(docx_files)
    logger.info(f"📚 Verarbeite {len(pdf_files)} PDFs + {len(docx_files)} DOCX = {total_files} Dokumente...")
    
    all_chunks = []
    
    # ===== PDFs VERARBEITEN =====
    for pdf_file in sorted(pdf_files):
        filename = pdf_file.name
        
        # Chunk-Size aus Statistiken ermitteln
        if vs.doc_stats is not None and filename in vs.doc_stats.index:
            word_count = int(vs.doc_stats.loc[filename, 'words'])
            chunk_size_adaptive, overlap_adaptive = get_chunk_size_by_words(word_count)
            
            logger.info(f"📄 {filename}: {word_count} Wörter → "
                        f"Chunk {chunk_size_adaptive}/{overlap_adaptive}")
        else:
            # Fallback
            logger.warning(f"⚠️ {filename} nicht in Statistiken, nutze Default 400/100")
            chunk_size_adaptive = 400
            overlap_adaptive = 100
        
        # Loader mit angepasster Chunk-Size
        loader_temp = LicenseDocumentLoader(
            chunk_size=chunk_size_adaptive,
            chunk_overlap=overlap_adaptive
        )
        
        # Nur dieses eine PDF laden
        chunks = loader_temp.load_single_pdf(pdf_file)
        
        logger.info(f"  → {len(chunks)} Chunks erstellt")
        all_chunks.extend(chunks)
    
    # ===== DOCX VERARBEITEN =====
    for docx_file in sorted(docx_files):
        filename = docx_file.name
        
        # DOCX haben meist viel Text → Standard Chunk-Size
        chunk_size_adaptive = 400
        overlap_adaptive = 100
        
        logger.info(f"📄 {filename} (DOCX) → Chunk {chunk_size_adaptive}/{overlap_adaptive}")
        
        # Loader
        loader_temp = LicenseDocumentLoader(
            chunk_size=chunk_size_adaptive,
            chunk_overlap=overlap_adaptive
        )
        
        # DOCX laden
        chunks = loader_temp.load_docx(docx_file)
        
        logger.info(f"  → {len(chunks)} Chunks erstellt")
        all_chunks.extend(chunks)

    logger.info(f"✅ Gesamt: {len(all_chunks)} Chunks aus {total_files} Dokumenten")
    
    # Zu Vectorstore hinzufügen
    vs.add_documents(all_chunks)
    
    # Statistiken
    stats = vs.get_stats()
    logger.info("="*70)
    logger.info("📊 FERTIG")
    logger.info("="*70)
    logger.info(f"Collection:  {stats['collection_name']}")
    logger.info(f"Dokumente:   {stats['total_documents']:,}")
    logger.info(f"Gespeichert: {stats['persist_directory']}")
    logger.info("="*70)
    
    return vs


if __name__ == "__main__":
    # Vectorstore neu bauen
    vs = build_vectorstore()
    
    # Testsuche
    results = vs.search("Was ist Sub-Capacity Lizenzierung?", k=3)
    
    print("\n🔍 TEST-SUCHE:\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result['distance']:.4f}")
        print(f"   Quelle: {result['metadata'].get('source', 'unknown')}")
        print(f"   Text: {result['text'][:200]}...\n")