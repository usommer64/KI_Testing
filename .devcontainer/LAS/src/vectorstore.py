#%%
"""
Vectorstore für IBM Lizenzierungsdokumente
Verwendet ChromaDB + BGE-Large-en-v1.5 Embeddings
Mit adaptiver UND fester Chunk-Größe (Flag-gesteuert)
"""

from pathlib import Path
from typing import List, Optional
import logging
import uuid

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LicenseVectorStore:
    """
    Vektordatenbank für Lizenzdokumente.
    
    Features:
    - BGE-Large-en-v1.5 Embeddings (Top-Qualität)
    - ChromaDB (persistent, lokal)
    - Asymmetrische Suche (Query-Prefix)
    - Adaptive ODER Fixed Chunk-Größe (Experiment-Flag)
    """
    
    def __init__(
        self,
        collection_name: str = "ibm_licenses",
        persist_directory: str = None,
        embedding_model: str = "BAAI/bge-large-en-v1.5",
        use_adaptive_chunking: bool = True  # ← Flag für Experiment
    ):
        """
        Args:
            collection_name: Name der ChromaDB Collection
            persist_directory: Pfad für persistente Speicherung
            embedding_model: Hugging Face Model-name
            use_adaptive_chunking: True = adaptive Größen, False = fix 400/100
        """
        self.collection_name = collection_name
        self.use_adaptive_chunking = use_adaptive_chunking
        
        # Default: Speichern neben src/
        if persist_directory is None:
            persist_directory = str(Path(__file__).parent.parent / "data" / "chroma_db")
        
        self.persist_directory = persist_directory
        
        # Embedding-Modell laden
        logger.info(f"📥 Lade Embedding-Modell: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        logger.info(f"✅ Modell geladen: {self.embedding_model.get_sentence_embedding_dimension()} Dimensionen")
        
        # Dokument-Statistiken laden (nur wenn adaptive)
        if use_adaptive_chunking:
            stats_file = Path(__file__).parent / "document_stats.csv"
            if stats_file.exists():
                import pandas as pd
                self.doc_stats = pd.read_csv(stats_file)
                logger.info(f"✅ Dokument-Statistiken geladen: {len(self.doc_stats)} Docs")
                
                # Index für schnellen Lookup
                self.doc_stats.set_index('file_name', inplace=True)
            else:
                self.doc_stats = None
                logger.warning("⚠️  Keine document_stats.csv gefunden - nutze adaptive Defaults")
        else:
            # Fixed mode
            logger.info("🔧 EXPERIMENT: Feste Chunk-Größe 400/100 (kein Adaptive Chunking)")
            self.doc_stats = None
            self.fixed_chunk_size = 400
            self.fixed_chunk_overlap = 100
        
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
                metadata={"description": "IBM Licensing Documents"}
            )
            logger.info(f"✅ Collection '{collection_name}' erstellt")
    
    def _get_chunk_params(self, file_name: str, word_count: int) -> tuple:
        """
        Bestimmt optimale Chunk-Parameter.
        
        Adaptive Mode: Basiert auf Dokumentgröße
        Fixed Mode: Immer 400/100
        """
        # Fixed mode?
        if hasattr(self, 'fixed_chunk_size'):
            return self.fixed_chunk_size, self.fixed_chunk_overlap
        
        # Adaptive mode: Falls Stats vorhanden, nutze diese
        if self.doc_stats is not None and file_name in self.doc_stats.index:
            row = self.doc_stats.loc[file_name]
            return int(row['recommended_chunk_size']), int(row['recommended_overlap'])
        
        # Adaptive mode: Fallback auf Größen-basierte Logik
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
    
    def load_and_process_documents(self, data_dir: Path) -> List[Document]:
        """
        Lädt und verarbeitet Dokumente mit adaptiver ODER fester Chunk-Größe.
        
        Args:
            data_dir: Verzeichnis mit PDF/DOCX-Dateien
            
        Returns:
            Liste von Document-Objekten (Chunks)
        """
        all_chunks = []
        
        # PDF-Dateien finden
        pdf_files = list(data_dir.glob("*.pdf"))
        pdf_files_upper = list(data_dir.glob("*.PDF"))
        all_pdfs = pdf_files + pdf_files_upper
        
        # DOCX-Dateien finden
        docx_files = list(data_dir.glob("*.docx"))
        docx_files_upper = list(data_dir.glob("*.DOCX"))
        all_docx = docx_files + docx_files_upper
        
        total_files = len(all_pdfs) + len(all_docx)
        logger.info(f"📚 Verarbeite {len(all_pdfs)} PDFs + {len(all_docx)} DOCX = {total_files} Dokumente...")
        
        # PDFs verarbeiten
        for pdf_file in all_pdfs:
            try:
                # Wortanzahl schätzen
                import PyPDF2
                with open(pdf_file, 'rb') as f:
                    pdf = PyPDF2.PdfReader(f)
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text()
                    word_count = len(text.split())
                
                # Chunk-Parameter bestimmen
                chunk_size, overlap = self._get_chunk_params(pdf_file.name, word_count)
                
                logger.info(f"📄 {pdf_file.name}: {word_count} Wörter → Chunk {chunk_size}/{overlap}")
                
                # PDF laden
                pdf_loader = PyPDFLoader(str(pdf_file))
                pages = pdf_loader.load()
                
                # Splitter mit aktuellen Parametern
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=overlap,
                    length_function=len,
                    separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
                )
                
                chunks = splitter.split_documents(pages)
                
                # Metadata erweitern
                for chunk in chunks:
                    chunk.metadata['word_count'] = word_count
                    chunk.metadata['chunk_size'] = chunk_size
                    chunk.metadata['overlap'] = overlap
                
                all_chunks.extend(chunks)
                logger.info(f"  → {len(chunks)} Chunks erstellt")
                
            except Exception as e:
                logger.error(f"❌ Fehler bei {pdf_file.name}: {e}")
        
        # DOCX verarbeiten
        for docx_file in all_docx:
            try:
                # Wortanzahl aus DOCX
                from docx import Document as DocxDocument
                doc = DocxDocument(docx_file)
                text = "\n".join([para.text for para in doc.paragraphs])
                word_count = len(text.split())
                
                # Chunk-Parameter bestimmen
                chunk_size, overlap = self._get_chunk_params(docx_file.name, word_count)
                
                logger.info(f"📄 {docx_file.name} (DOCX): {word_count} Wörter → Chunk {chunk_size}/{overlap}")
                
                # DOCX laden
                docx_loader = Docx2txtLoader(str(docx_file))
                doc_content = docx_loader.load()
                
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=overlap,
                    length_function=len,
                    separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
                )
                
                chunks = splitter.split_documents(doc_content)
                
                # Metadata erweitern
                for chunk in chunks:
                    chunk.metadata['word_count'] = word_count
                    chunk.metadata['chunk_size'] = chunk_size
                    chunk.metadata['overlap'] = overlap
                
                all_chunks.extend(chunks)
                logger.info(f"  → {len(chunks)} Chunks erstellt")
                
            except Exception as e:
                logger.error(f"❌ Fehler bei {docx_file.name}: {e}")
        
        return all_chunks
    
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
            convert_to_numpy=True,
            batch_size=32
        )
        
        return embeddings.tolist()
    
    def add_documents(self, documents: List[Document]) -> None:
        """
        Fügt Dokumente zur Vektordatenbank hinzu.
        """
        if not documents:
            logger.warning("Keine Dokumente zum Hinzufügen")
            return
        
        logger.info(f"📄 Füge {len(documents)} Dokumente hinzu...")
        
        # Texte und Metadaten extrahieren
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        
        # UUID-IDs generieren
        ids = [str(uuid.uuid4()) for _ in range(len(documents))]
        
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
    
    def search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Optional[dict] = None
    ) -> List[dict]:
        """
        Sucht ähnliche Dokumente.
        
        Args:
            query: Suchanfrage
            k: Anzahl Ergebnisse
            filter_metadata: Optional: Filter für Metadaten
            
        Returns:
            Liste von Ergebnissen mit Text, Metadaten, Score
        """
        logger.info(f"🔍 Suche: '{query}'")
        
        # Query-Embedding erstellen
        query_embedding = self.embed_texts([query], is_query=True)[0]
        
        # ChromaDB-Suche
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter_metadata
        )
        
        # Ergebnisse formatieren
        formatted_results = []
        for i in range(len(results['ids'][0])):
            result = {
                "id": results['ids'][0][i],
                "text": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "score": results['distances'][0][i]
            }
            formatted_results.append(result)
        
        logger.info(f"✅ {len(formatted_results)} Ergebnisse gefunden")
        return formatted_results
    
    def get_stats(self) -> dict:
        """Gibt Statistiken über die Datenbank zurück."""
        count = self.collection.count()
        
        return {
            "collection_name": self.collection_name,
            "total_documents": count,
            "persist_directory": self.persist_directory,
            "embedding_model": str(self.embedding_model),
            "embedding_dimensions": self.embedding_model.get_sentence_embedding_dimension(),
            "adaptive_chunking": self.use_adaptive_chunking
        }


def main():
    """
    Build-Script: Erstellt Vectorstore.
    Nutze use_adaptive_chunking Flag für Experimente!
    """
    from pathlib import Path
    
    print("=" * 70)
    print("🏗️  BAUE VECTORSTORE MIT ADAPTIVER CHUNK-SIZE + DOCX-SUPPORT")
    print("=" * 70)
    
    # Pfad zu Dokumenten
    data_dir = Path(__file__).parent.parent / "data"
    
    # Vectorstore mit ADAPTIVE Chunking
    vectorstore = LicenseVectorStore(
        collection_name="ibm_licenses",
        embedding_model="BAAI/bge-large-en-v1.5",
        use_adaptive_chunking=True  # ← Für Fixed: False
    )
    
    # Dokumente laden und verarbeiten
    documents = vectorstore.load_and_process_documents(data_dir)
    logger.info(f"✅ Gesamt: {len(documents)} Chunks aus {len(list(data_dir.glob('*.pdf')) + list(data_dir.glob('*.PDF')) + list(data_dir.glob('*.docx')) + list(data_dir.glob('*.DOCX')))} Dokumenten")
    
    # Zu Vectorstore hinzufügen
    vectorstore.add_documents(documents)
    
    # Stats
    stats = vectorstore.get_stats()
    print("=" * 70)
    print("📊 FERTIG")
    print("=" * 70)
    print(f"Collection:  {stats['collection_name']}")
    print(f"Dokumente:   {stats['total_documents']:,}")
    print(f"Gespeichert: {stats['persist_directory']}")
    print("=" * 70)
    
    # Test-Suche
    print("\n🔍 TEST-SUCHE:")
    print()
    results = vectorstore.search("Was ist Sub-Capacity Lizenzierung?", k=3)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result['score']:.4f}")
        print(f"   Quelle: {result['metadata']['source']}")
        print(f"   Text: {result['text'][:200]}...\n")


if __name__ == "__main__":
    main()