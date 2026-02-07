#%%
"""
Vectorstore für IBM Lizenzierungsdokumente
Verwendet ChromaDB + BGE-Large-en-v1.5 Embeddings
"""

from pathlib import Path
from typing import List, Optional
import logging

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from langchain.schema import Document

from loader import LicenseDocumentLoader

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
        
        # ChromaDB Client erstellen
        logger.info(f"📂 Initialisiere ChromaDB in: {persist_directory}")
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False # Keine Telemetrie
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
            documents: Liste von LangChain Document-Objekten
        """
        if not documents:
            logger.warning("⚠️  Keine Dokumente zum Hinzufügen!")
            return
        
        logger.info(f"📝 Bereite {len(documents)} Dokumente vor...")
        
        # Texte extrahieren
        texts = [doc.page_content for doc in documents]
        
        # Metadaten vorbereiten (ChromaDB akzeptiert nur bestimmte Typen)
        metadatas = []
        for doc in documents:
            metadata = {
                "source": str(doc.metadata.get("source", "unknown")),
                "file_name": doc.metadata.get("file_name", "unknown"),
                "file_type": doc.metadata.get("file_type", "unknown"),
            }
            # Page nur hinzufügen wenn vorhanden
            if "page" in doc.metadata:
                metadata["page"] = int(doc.metadata["page"])
            
            metadatas.append(metadata)
        
        # IDs generieren (eindeutige IDs für jedes Dokument)
        ids = [f"doc_{i}" for i in range(len(documents))]
        
        # Embeddings erstellen
        logger.info(f"🔢 Erstelle Embeddings (das dauert ~30 Sekunden)...")
        embeddings = self.embed_texts(texts, is_query=False)
        
        # Zu ChromaDB hinzufügen
        logger.info(f"💾 Speichere in ChromaDB...")
        self.collection.add(
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings,
            ids=ids
        )
        
        logger.info(f"✅ {len(documents)} Dokumente hinzugefügt!")
        logger.info(f"📊 Collection enthält jetzt {self.collection.count()} Dokumente")
    
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
                Beispiel: {"file_type": "pdf"}
            
        Returns:
            Liste von Ergebnissen mit Text, Metadaten, Score
        """
        logger.info(f"🔍 Suche: '{query}'")
        
        # Query-Embedding erstellen (mit Prefix!)
        query_embedding = self.embed_texts([query], is_query=True)[0]
        
        # ChromaDB-Suche
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter_metadata  # Optional: Filter
        )
        
        # Ergebnisse formatieren
        formatted_results = []
        for i in range(len(results['ids'][0])):
            result = {
                "id": results['ids'][0][i],
                "text": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "score": results['distances'][0][i]  # Niedriger = ähnlicher
            }
            formatted_results.append(result)
        
        logger.info(f"✅ {len(formatted_results)} Ergebnisse gefunden")
        return formatted_results
    
    def reset(self) -> None:
        """Löscht alle Dokumente aus der Collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"🗑️  Collection '{self.collection_name}' gelöscht")
            
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "IBM Licensing Documents"}
            )
            logger.info(f"✅ Collection '{self.collection_name}' neu erstellt")
        except Exception as e:
            logger.error(f"❌ Fehler beim Reset: {e}")
    
    def get_stats(self) -> dict:
        """Gibt Statistiken über die Datenbank zurück."""
        count = self.collection.count()
        
        # Sample-Dokument für Metadaten-Info
        sample = None
        if count > 0:
            sample = self.collection.get(limit=1)
        
        return {
            "collection_name": self.collection_name,
            "total_documents": count,
            "persist_directory": self.persist_directory,
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_model.get_sentence_embedding_dimension(),
            "sample_metadata": sample['metadatas'][0] if sample else None
        }


def main():
    """Test-Funktion: Lädt Dokumente und erstellt Vektordatenbank."""
    from pathlib import Path
    
    print("=" * 70)
    print("🚀 VECTORSTORE SETUP")
    print("=" * 70)
    
    # Pfad zu Dokumenten
    data_dir = Path(__file__).parent.parent / "data"
    
    # 1. Dokumente laden
    print("\n📚 SCHRITT 1: Dokumente laden")
    print("-" * 70)
    loader = LicenseDocumentLoader(chunk_size=1000, chunk_overlap=200)
    chunks = loader.load_and_split(data_dir)
    
    if not chunks:
        print("❌ Keine Dokumente gefunden!")
        return
    
    print(f"✅ {len(chunks)} Chunks geladen")
    
    # 2. Vectorstore erstellen
    print("\n🔢 SCHRITT 2: Vectorstore erstellen")
    print("-" * 70)
    vectorstore = LicenseVectorStore(
        collection_name="ibm_licenses",
        embedding_model="BAAI/bge-large-en-v1.5"
    )
    
    # 3. Dokumente hinzufügen
    print("\n💾 SCHRITT 3: Dokumente embedden und speichern")
    print("-" * 70)
    vectorstore.add_documents(chunks)
    
    # 4. Statistiken
    print("\n📊 SCHRITT 4: Statistiken")
    print("-" * 70)
    stats = vectorstore.get_stats()
    print(f"Collection: {stats['collection_name']}")
    print(f"Dokumente: {stats['total_documents']}")
    print(f"Dimensionen: {stats['embedding_dimensions']}")
    print(f"Speicherort: {stats['persist_directory']}")
    
    # 5. Test-Queries
    print("\n🔍 SCHRITT 5: Test-Queries")
    print("=" * 70)
    
    test_queries = [
        "Was ist IBM BYOSL?",
        "Wie funktioniert Container-Lizenzierung?",
        "Was bedeutet PVU?",
        "Virtualisierung und Sub-Capacity",
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        print("-" * 70)
        
        results = vectorstore.search(query, k=3)
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Score: {result['score']:.4f}")
            print(f"   Quelle: {result['metadata']['file_name']}")
            if 'page' in result['metadata']:
                print(f"   Seite: {result['metadata']['page']}")
            print(f"   Text: {result['text'][:150]}...")
    
    print("\n" + "=" * 70)
    print("✅ VECTORSTORE SETUP ABGESCHLOSSEN!")
    print("=" * 70)


if __name__ == "__main__":
    main()