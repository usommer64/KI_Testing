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
    
    def load_single_pdf(self, pdf_path: Path) -> List[Document]:
        """
        Lädt ein einzelnes PDF mit den aktuellen Chunk-Einstellungen.
    
        Args:
            pdf_path: Pfad zum PDF
        
        Returns:
            Liste von Document-Chunks
        """
        try:
            loader = PyPDFLoader(str(pdf_path))
            pages = loader.load()
            
            # In Chunks aufteilen
            chunks = self.text_splitter.split_documents(pages)
            
            # Metadaten hinzufügen
            for chunk in chunks:
                chunk.metadata.update({
                    "source": str(pdf_path),
                    "file_type": "pdf",
                    "file_name": pdf_path.name
                })
            
            logger.info(f"✅ PDF geladen: {pdf_path.name} ({len(chunks)} Chunks)")
            return chunks
            
        except Exception as e:
            logger.error(f"❌ Fehler bei {pdf_path.name}: {e}")
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
            logger.error(f"❌ Fehler bei {file_path.name}: {e}")
            return []
    
    def load_docx(self, file_path: Path) -> List[Document]:
        """
        Lädt ein DOCX-Dokument.
        
        Args:
            file_path: Pfad zum DOCX
        
        Returns:
            Liste von Document-Chunks
        """
        try:
            loader = Docx2txtLoader(str(file_path))
            docs = loader.load()
            
            # Metadaten hinzufügen (vor dem Chunking)
            for doc in docs:
                doc.metadata.update({
                    "source": str(file_path),
                    "file_type": "docx",
                    "file_name": file_path.name
                })
            
            # In Chunks aufteilen
            chunks = self.text_splitter.split_documents(docs)
            
            logger.info(f"✅ DOCX geladen: {file_path.name} ({len(chunks)} Chunks)")
            return chunks
            
        except Exception as e:
            logger.error(f"❌ Fehler bei {file_path.name}: {e}")
            return []
    
    def load_directory(self, directory: Path) -> List[Document]:
        """
        Lädt alle unterstützten Dokumente aus einem Verzeichnis.
        
        Args:
            directory: Pfad zum Verzeichnis
        
        Returns:
            Liste aller Document-Chunks
        """
        all_chunks = []
        
        # Zähler für Statistik
        stats = {"pdf": 0, "markdown": 0, "docx": 0}
        
        # PDFs laden
        for pdf_file in directory.glob("**/*.pdf"):
            chunks = self.load_single_pdf(pdf_file)
            all_chunks.extend(chunks)
            stats["pdf"] += 1
        
        for pdf_file in directory.glob("**/*.PDF"):  # Auch Großbuchstaben
            chunks = self.load_single_pdf(pdf_file)
            all_chunks.extend(chunks)
            stats["pdf"] += 1
        
        # Markdown laden
        for md_file in directory.glob("**/*.md"):
            docs = self.load_markdown(md_file)
            chunks = self.text_splitter.split_documents(docs)
            all_chunks.extend(chunks)
            stats["markdown"] += 1
        
        # DOCX laden
        for docx_file in directory.glob("**/*.docx"):
            chunks = self.load_docx(docx_file)
            all_chunks.extend(chunks)
            stats["docx"] += 1
        
        for docx_file in directory.glob("**/*.DOCX"):  # Auch Großbuchstaben
            chunks = self.load_docx(docx_file)
            all_chunks.extend(chunks)
            stats["docx"] += 1
        
        # Statistik ausgeben
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 DOKUMENTE GELADEN:")
        logger.info(f"  - PDFs:     {stats['pdf']}")
        logger.info(f"  - Markdown: {stats['markdown']}")
        logger.info(f"  - DOCX:     {stats['docx']}")
        logger.info(f"  - GESAMT:   {sum(stats.values())} Dateien")
        logger.info(f"  - CHUNKS:   {len(all_chunks)}")
        logger.info(f"{'='*70}\n")
        
        return all_chunks
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Splittet Dokumente in Chunks (falls noch nicht geschehen).
        
        Args:
            documents: Liste von Dokumenten
        
        Returns:
            Liste von Chunks
        """
        return self.text_splitter.split_documents(documents)


# ===== HELPER FUNKTION =====

def count_words(text: str) -> int:
    """Zählt Wörter in einem Text."""
    return len(text.split())


def analyze_document(doc_path: Path) -> Dict[str, Any]:
    """
    Analysiert ein Dokument und gibt Statistiken zurück.
    
    Args:
        doc_path: Pfad zum Dokument
    
    Returns:
        Dict mit Statistiken (pages, words, chars, etc.)
    """
    loader = LicenseDocumentLoader()
    
    if doc_path.suffix.lower() == '.pdf':
        chunks = loader.load_single_pdf(doc_path)
    elif doc_path.suffix.lower() == '.docx':
        chunks = loader.load_docx(doc_path)
    elif doc_path.suffix.lower() == '.md':
        docs = loader.load_markdown(doc_path)
        chunks = loader.split_documents(docs)
    else:
        return {"error": f"Nicht unterstützter Dateityp: {doc_path.suffix}"}
    
    # Statistiken berechnen
    total_chars = sum(len(chunk.page_content) for chunk in chunks)
    total_words = sum(count_words(chunk.page_content) for chunk in chunks)
    
    return {
        "filename": doc_path.name,
        "file_type": doc_path.suffix.lower(),
        "chunks": len(chunks),
        "total_chars": total_chars,
        "total_words": total_words,
        "avg_chunk_size": total_chars / len(chunks) if chunks else 0,
        "avg_words_per_chunk": total_words / len(chunks) if chunks else 0,
    }


# ===== MAIN (für schnelle Tests) =====

if __name__ == "__main__":
    # Quick Test
    data_dir = Path(__file__).parent.parent / "data" / "pdfs"
    
    if data_dir.exists():
        print(f"📂 Teste Loader mit: {data_dir}")
        
        loader = LicenseDocumentLoader(chunk_size=500, chunk_overlap=100)
        chunks = loader.load_directory(data_dir)
        
        print(f"\n✅ {len(chunks)} Chunks geladen")
        
        # Zeige Beispiel
        if chunks:
            print("\n" + "="*70)
            print("📄 BEISPIEL-CHUNK:")
            print("="*70)
            chunk = chunks[0]
            print(f"Datei: {chunk.metadata.get('file_name', 'unknown')}")
            print(f"Typ:   {chunk.metadata.get('file_type', 'unknown')}")
            print(f"Seite: {chunk.metadata.get('page', 'N/A')}")
            print(f"\nInhalt (erste 300 Zeichen):")
            print(chunk.page_content[:300])
            print("="*70)
    else:
        print(f"❌ Verzeichnis nicht gefunden: {data_dir}")