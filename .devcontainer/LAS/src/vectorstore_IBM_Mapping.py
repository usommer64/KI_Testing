# vectorstore.py
import os
import logging
from typing import List, Dict, Any, Optional
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import hashlib
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# HELPER-FUNKTION: IBM Produkt-Mapping einlesen
# ============================================================================

def load_ibm_product_mapping(mapping_file: str = "product_mapping.txt") -> Dict[str, Dict[str, str]]:
    """
    Liest die IBM Produkt-Mapping-Datei ein und erstellt ein Dictionary.
    
    Args:
        mapping_file: Pfad zur Mapping-Datei (Standard: product_mapping.txt)
    
    Returns:
        Dictionary mit license_code als Key und product_name, language, filename als Values
        Beispiel: {
            'L-CHSG-4QYF8X': {
                'product_name': 'IBM Guardium Data Encryption v5.1.1',
                'language': 'en',
                'filename': 'L-CHSG-4QYF8X_en.pdf'
            },
            ...
        }
    """
    mapping = {}
    
    try:
        if not os.path.exists(mapping_file):
            logger.warning(f"IBM Product Mapping-Datei nicht gefunden: {mapping_file}")
            return mapping
        
        with open(mapping_file, 'r', encoding='utf-8') as f:
            # Erste Zeile überspringen (Header)
            next(f)
            
            for line_num, line in enumerate(f, start=2):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split(',')
                if len(parts) != 4:
                    logger.warning(f"Zeile {line_num} hat ungültiges Format: {line}")
                    continue
                
                license_code, product_name, language, filename = parts
                
                mapping[license_code] = {
                    'product_name': product_name,
                    'language': language,
                    'filename': filename
                }
        
        logger.info(f"IBM Product Mapping erfolgreich geladen: {len(mapping)} Einträge")
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der IBM Product Mapping-Datei: {e}")
    
    return mapping


# ============================================================================
# METADATA-EXTRAKTION MIT IBM-MAPPING
# ============================================================================

def extract_metadata_from_filename(filename: str, ibm_mapping: Optional[Dict[str, Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    Extrahiert Metadaten aus dem Dateinamen.
    
    Unterstützte Formate:
    - IBM: L-XXXX-XXXXXX_lang.pdf (z.B. L-CHSG-4QYF8X_en.pdf)
    - Microsoft: beliebige PDF-Dateien
    
    Args:
        filename: Name der Datei
        ibm_mapping: Dictionary mit IBM Produkt-Mapping (optional)
    
    Returns:
        Dictionary mit Metadaten
    """
    metadata = {
        'source': filename,
        'manufacturer': 'Unknown',
        'product_name': 'Unknown',
        'language': 'Unknown',
        'license_code': None
    }
    
    # IBM Format erkennen: L-XXXX-XXXXXX_lang.pdf
    ibm_pattern = r'^(L-[A-Z0-9]{4}-[A-Z0-9]{6})_([a-z]{2})\.pdf$'
    match = re.match(ibm_pattern, filename, re.IGNORECASE)
    
    if match:
        license_code = match.group(1).upper()
        language = match.group(2).lower()
        
        metadata['manufacturer'] = 'IBM'
        metadata['license_code'] = license_code
        metadata['language'] = language
        
        # Wenn Mapping verfügbar ist, Produktnamen nachschlagen
        if ibm_mapping and license_code in ibm_mapping:
            product_info = ibm_mapping[license_code]
            metadata['product_name'] = product_info['product_name']
            
            # Prüfen ob Language im Mapping mit Filename übereinstimmt
            if product_info['language'] != language:
                logger.warning(
                    f"Language Mismatch für {filename}: "
                    f"Filename hat '{language}', Mapping hat '{product_info['language']}'"
                )
        else:
            metadata['product_name'] = f"IBM Product {license_code}"
            if not ibm_mapping:
                logger.debug(f"Kein IBM Mapping verfügbar für {filename}")
            else:
                logger.warning(f"License Code {license_code} nicht im IBM Mapping gefunden")
    
    else:
        # Annahme: Microsoft oder anderer Hersteller
        metadata['manufacturer'] = 'Microsoft'
        metadata['product_name'] = filename.replace('.pdf', '')
        
        # Versuche Sprache aus Dateinamen zu extrahieren (z.B. _de.pdf, _en.pdf)
        lang_match = re.search(r'_([a-z]{2})\.pdf$', filename, re.IGNORECASE)
        if lang_match:
            metadata['language'] = lang_match.group(1).lower()
    
    return metadata


# ============================================================================
# VECTORSTORE-KLASSE
# ============================================================================

class VectorStoreManager:
    """Manager für ChromaDB Vector Store mit Unterstützung für IBM und Microsoft Lizenzen"""
    
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "license_documents",
        embedding_model: str = "text-embedding-3-small",
        ibm_mapping_file: str = "product_mapping.txt"
    ):
        """
        Initialisiert den VectorStore Manager.
        
        Args:
            persist_directory: Verzeichnis für ChromaDB Persistenz
            collection_name: Name der ChromaDB Collection
            embedding_model: OpenAI Embedding Model
            ibm_mapping_file: Pfad zur IBM Product Mapping-Datei
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        
        # IBM Mapping laden
        self.ibm_mapping = load_ibm_product_mapping(ibm_mapping_file)
        
        # Embedding-Modell initialisieren
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        
        # VectorStore initialisieren
        self.vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory
        )
        
        logger.info(f"VectorStore initialisiert: {collection_name}")
        logger.info(f"IBM Product Mapping: {len(self.ibm_mapping)} Produkte geladen")
    
    def create_text_splitter(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> RecursiveCharacterTextSplitter:
        """
        Erstellt einen Text Splitter für die Dokumenten-Aufteilung.
        
        Args:
            chunk_size: Größe der Text-Chunks
            chunk_overlap: Überlappung zwischen Chunks
        
        Returns:
            RecursiveCharacterTextSplitter Instanz
        """
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def generate_doc_id(self, content: str, source: str, chunk_index: int) -> str:
        """
        Generiert eine eindeutige ID für einen Dokument-Chunk.
        
        Args:
            content: Chunk-Inhalt
            source: Quell-Datei
            chunk_index: Index des Chunks
        
        Returns:
            Hash-basierte eindeutige ID
        """
        unique_string = f"{source}_{chunk_index}_{content[:100]}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def add_documents(
        self,
        documents: List[Document],
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[str]:
        """
        Fügt Dokumente zum VectorStore hinzu.
        
        Args:
            documents: Liste von LangChain Documents
            chunk_size: Größe der Text-Chunks
            chunk_overlap: Überlappung zwischen Chunks
        
        Returns:
            Liste der generierten Dokument-IDs
        """
        # Text-Splitter erstellen
        text_splitter = self.create_text_splitter(chunk_size, chunk_overlap)
        
        # Dokumente in Chunks aufteilen
        chunks = text_splitter.split_documents(documents)
        
        # Metadaten mit IBM Mapping anreichern
        for chunk in chunks:
            filename = os.path.basename(chunk.metadata.get('source', ''))
            extracted_metadata = extract_metadata_from_filename(filename, self.ibm_mapping)
            chunk.metadata.update(extracted_metadata)
        
        # Eindeutige IDs generieren
        ids = [
            self.generate_doc_id(
                chunk.page_content,
                chunk.metadata.get('source', 'unknown'),
                i
            )
            for i, chunk in enumerate(chunks)
        ]
        
        # Zu VectorStore hinzufügen
        self.vectorstore.add_documents(documents=chunks, ids=ids)
        
        logger.info(f"{len(chunks)} Chunks zum VectorStore hinzugefügt")
        return ids
    
    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Führt eine Ähnlichkeitssuche durch.
        
        Args:
            query: Suchanfrage
            k: Anzahl der zurückzugebenden Ergebnisse
            filter_dict: Optionale Metadaten-Filter
        
        Returns:
            Liste von relevanten Dokumenten
        """
        if filter_dict:
            return self.vectorstore.similarity_search(
                query,
                k=k,
                filter=filter_dict
            )
        return self.vectorstore.similarity_search(query, k=k)
    
    def get_retriever(self, search_kwargs: Optional[Dict[str, Any]] = None):
        """
        Gibt einen Retriever für RAG zurück.
        
        Args:
            search_kwargs: Optionale Suchparameter
        
        Returns:
            VectorStore Retriever
        """
        if search_kwargs is None:
            search_kwargs = {"k": 4}
        
        return self.vectorstore.as_retriever(search_kwargs=search_kwargs)
    
    def delete_collection(self):
        """Löscht die gesamte Collection."""
        self.vectorstore.delete_collection()
        logger.info(f"Collection {self.collection_name} gelöscht")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Gibt Statistiken über die Collection zurück.
        
        Returns:
            Dictionary mit Statistiken
        """
        collection = self.vectorstore._collection
        count = collection.count()
        
        return {
            'document_count': count,
            'collection_name': self.collection_name,
            'ibm_products_mapped': len(self.ibm_mapping)
        }


# ============================================================================
# BEISPIEL-VERWENDUNG
# ============================================================================

if __name__ == "__main__":
    # Logging konfigurieren
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # VectorStore Manager erstellen
    vs_manager = VectorStoreManager(
        persist_directory="./chroma_db",
        collection_name="license_documents",
        ibm_mapping_file="product_mapping.txt"
    )
    
    # Beispiel: Metadaten aus Dateinamen extrahieren
    test_filenames = [
        "L-CHSG-4QYF8X_en.pdf",
        "L-YRHY-YWPJ3V_de.pdf",
        "Microsoft_Office_365_de.pdf",
        "unknown_document.pdf"
    ]
    
    print("\n=== Metadaten-Extraktion Beispiele ===\n")
    for filename in test_filenames:
        metadata = extract_metadata_from_filename(filename, vs_manager.ibm_mapping)
        print(f"Datei: {filename}")
        print(f"  Hersteller: {metadata['manufacturer']}")
        print(f"  Produkt: {metadata['product_name']}")
        print(f"  Sprache: {metadata['language']}")
        print(f"  License Code: {metadata.get('license_code', 'N/A')}")
        print()
    
    # Statistiken ausgeben
    stats = vs_manager.get_collection_stats()
    print(f"\n=== VectorStore Statistiken ===")
    print(f"Collection: {stats['collection_name']}")
    print(f"Dokumente: {stats['document_count']}")
    print(f"IBM Produkte im Mapping: {stats['ibm_products_mapped']}")