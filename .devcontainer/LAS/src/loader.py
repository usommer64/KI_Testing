"""
Document Loader für IBM Lizenzierungsdokumente
Unterstützt: PDF, Markdown, DOCX
"""
#%%
from pathlib import Path
from typing import List, Dict, Any
import logging

from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredMarkdownLoader,
    Docx2txtLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LicenseDocumentLoader:
    """
    Lädt Lizenzdokumente (PDF, MD, DOCX) und splittet sie in Chunks.
    
    Optimiert für:
    - IBM Lizenzierungsdokumente
    - Software-Lizenztexte
    - Vertragstexte
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: List[str] = None
    ):
        """
        Args:
            chunk_size: Größe der Text-Chunks in Zeichen
            chunk_overlap: Überlappung zwischen Chunks
            separators: Trennzeichen für intelligentes Splitting
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Optimierte Separatoren für Lizenztexte
        if separators is None:
            separators = [
                "\n\n",  # Absätze
                "\n",    # Zeilen
                ". ",    # Sätze
                ", ",    # Kommas
                " ",     # Wörter
                ""       # Zeichen
            ]
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
        )
    
    def load_pdf(self, file_path: Path) -> List[Document]:
        """Lädt ein PDF-Dokument."""
        try:
            loader = PyPDFLoader(str(file_path))
            documents = loader.load()
            
            # Metadaten anreichern
            for doc in documents:
                doc.metadata.update({
                    "source": str(file_path),
                    "file_type": "pdf",
                    "file_name": file_path.name
                })
            
            logger.info(f"✅ PDF geladen: {file_path.name} ({len(documents)} Seiten)")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden von {file_path}: {e}")
            return []
    
    def load_markdown(self, file_path: Path) -> List[Document]:
        """Lädt ein Markdown-Dokument."""
        try:
            # Einfacher Ansatz: Als Text laden
            text = file_path.read_text(encoding='utf-8')
            
            # Document-Objekt erstellen
            doc = Document(
                page_content=text,
                metadata={
                    "source": str(file_path),
                    "file_type": "markdown",
                    "file_name": file_path.name
                }
            )
            
            logger.info(f"✅ Markdown geladen: {file_path.name}")
            return [doc]
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden von {file_path}: {e}")
            return []
    
    def load_docx(self, file_path: Path) -> List[Document]:
        """Lädt ein DOCX-Dokument."""
        try:
            loader = Docx2txtLoader(str(file_path))
            documents = loader.load()
            
            # Metadaten anreichern
            for doc in documents:
                doc.metadata.update({
                    "source": str(file_path),
                    "file_type": "docx",
                    "file_name": file_path.name
                })
            
            logger.info(f"✅ DOCX geladen: {file_path.name}")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden von {file_path}: {e}")
            return []
    
    def load_document(self, file_path: Path) -> List[Document]:
        """Lädt ein Dokument basierend auf der Dateiendung."""
        suffix = file_path.suffix.lower()
        
        if suffix == ".pdf":
            return self.load_pdf(file_path)
        elif suffix == ".md":
            return self.load_markdown(file_path)
        elif suffix == ".docx":
            return self.load_docx(file_path)
        else:
            logger.warning(f"⚠️  Nicht unterstützter Dateityp: {suffix}")
            return []
    
    def load_directory(self, directory: Path, recursive: bool = True) -> List[Document]:
        """
        Lädt alle unterstützten Dokumente aus einem Verzeichnis.
        
        Args:
            directory: Pfad zum Verzeichnis
            recursive: Auch Unterverzeichnisse durchsuchen
            
        Returns:
            Liste aller geladenen Dokumente
        """
        documents = []
        
        if not directory.exists():
            logger.error(f"❌ Verzeichnis nicht gefunden: {directory}")
            return documents
        
        # Pattern für unterstützte Dateitypen
        patterns = ["*.pdf", "*.md", "*.docx"]
        
        for pattern in patterns:
            if recursive:
                files = directory.rglob(pattern)
            else:
                files = directory.glob(pattern)
            
            for file_path in files:
                docs = self.load_document(file_path)
                documents.extend(docs)
        
        logger.info(f"📚 Insgesamt {len(documents)} Dokumente aus {directory.name} geladen")
        return documents
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Splittet Dokumente in Chunks.
        
        Args:
            documents: Liste von Dokumenten
            
        Returns:
            Liste von Chunks (Document-Objekte)
        """
        chunks = self.text_splitter.split_documents(documents)
        logger.info(f"✂️  {len(documents)} Dokumente in {len(chunks)} Chunks aufgeteilt")
        return chunks
    
    def load_and_split(self, directory: Path, recursive: bool = True) -> List[Document]:
        """
        Lädt Dokumente aus Verzeichnis und splittet sie direkt.
        
        Args:
            directory: Pfad zum Verzeichnis
            recursive: Auch Unterverzeichnisse durchsuchen
            
        Returns:
            Liste von Chunks
        """
        documents = self.load_directory(directory, recursive)
        if not documents:
            logger.warning("⚠️  Keine Dokumente geladen!")
            return []
        
        chunks = self.split_documents(documents)
        return chunks


def main():
    """Test-Funktion"""
    from pathlib import Path
    
    # Pfad zu Ihren IBM-Dokumenten
    data_dir = Path(__file__).parent.parent / "data"
    
    print(f"📂 Lade Dokumente aus: {data_dir}")
    print("-" * 60)
    
    # Loader erstellen
    loader = LicenseDocumentLoader(
        chunk_size=1000,
        chunk_overlap=200
    )
    
    # Dokumente laden und splitten
    chunks = loader.load_and_split(data_dir)
    
    print("-" * 60)
    print(f"✅ Fertig! {len(chunks)} Chunks erstellt")
    
    # Beispiel-Chunk anzeigen
    if chunks:
        print("\n" + "=" * 60)
        print("📄 Beispiel-Chunk:")
        print("=" * 60)
        chunk = chunks[0]
        print(f"Quelle: {chunk.metadata.get('file_name', 'unknown')}")
        print(f"Typ: {chunk.metadata.get('file_type', 'unknown')}")
        print(f"Seite: {chunk.metadata.get('page', 'N/A')}")
        print(f"\nInhalt (erste 500 Zeichen):\n{chunk.page_content[:500]}...")


if __name__ == "__main__":
    main()