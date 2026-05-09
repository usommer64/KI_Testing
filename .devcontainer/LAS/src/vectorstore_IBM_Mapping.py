#%%
"""
Vectorstore für IBM Lizenzierungsdokumente - COMPLETE VERSION
Kombiniert:
- Adaptive + Fixed Chunking (Flag-gesteuert)
- IBM Product Mapping Integration
- BGE-Large-en-v1.5 Embeddings (lokal, kein API-Call)
- Asymmetrische Suche (Query-Prefix)
- Document Stats Integration
- PDF + DOCX Support
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import logging
import uuid
import os
import re
from collections import Counter

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# HELPER-FUNKTION: IBM Produkt-Mapping einlesen
# ============================================================================

def load_ibm_product_mapping(mapping_file: str = "product_mapping.csv") -> Dict[str, Dict[str, str]]:
    """
    Liest die IBM Produkt-Mapping-Datei ein und erstellt ein Dictionary.
    
    Args:
        mapping_file: Pfad zur Mapping-Datei (Standard: product_mapping. im data-Ordner)
    
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
    
    # Suche Mapping-Datei im data-Ordner
    mapping_path = Path(__file__).parent.parent / "data" / mapping_file
    
    try:
        if not mapping_path.exists():
            logger.warning(f"⚠️  IBM Product Mapping-Datei nicht gefunden: {mapping_path}")
            return mapping
        
        with open(mapping_path, 'r', encoding='utf-8') as f:
            # Erste Zeile überspringen (Header)
            header = next(f)
            
            for line_num, line in enumerate(f, start=2):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split(',')
                if len(parts) != 4:
                    logger.warning(f"Zeile {line_num} hat ungültiges Format: {line}")
                    continue
                
                license_code, product_name, language, filename = parts
                
                mapping[license_code.strip()] = {
                    'product_name': product_name.strip(),
                    'language': language.strip(),
                    'filename': filename.strip()
                }
        
        logger.info(f"✅ IBM Product Mapping erfolgreich geladen: {len(mapping)} Einträge")
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der IBM Product Mapping-Datei: {e}")
    
    return mapping


# ============================================================================
# HELPER-FUNKTION: Metadaten aus Dateiname + Mapping extrahieren
# ============================================================================

def extract_metadata_from_filename(
    filename: str, 
    ibm_mapping: Optional[Dict[str, Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Extrahiert Metadaten aus dem Dateinamen mit IBM Mapping Support.
    
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
        'file_name': filename,
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
            if ibm_mapping is not None:  # Nur warnen wenn Mapping existiert
                logger.debug(f"License Code {license_code} nicht im IBM Mapping gefunden")
    
    else:
        # Annahme: IBM (für IBM-Pipeline; Dateinamen sind nicht immer L-....)
        metadata['manufacturer'] = 'IBM'
        metadata['product_name'] = filename.replace('.pdf', '').replace('.PDF', '')
        lang_match = re.search(r'_([a-z]{2})\.pdf$', filename, re.IGNORECASE)
        if lang_match:
            metadata['language'] = lang_match.group(1).lower()
    
    return metadata


def sanitize_metadata(metadata: dict) -> dict:
    """
    Bereinigt Metadaten für ChromaDB:
    - entfernt Keys mit None-Werten
    - entfernt verschachtelte Strukturen (dict/list/tuple/set)
    - behält nur str/int/float/bool als Value-Typen
    """
    if not isinstance(metadata, dict):
        return {}

    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple, set)):
            continue
        if not isinstance(value, (str, int, float, bool)):
            continue
        sanitized[key] = value

    return sanitized


# ============================================================================
# HAUPTKLASSE: LicenseVectorStore
# ============================================================================

class LicenseVectorStore:
    """
    Vektordatenbank für Lizenzdokumente.
    
    Features:
    - BGE-Large-en-v1.5 Embeddings (Top-Qualität, lokal)
    - ChromaDB (persistent, lokal)
    - Asymmetrische Suche (Query-Prefix)
    - Adaptive ODER Fixed Chunk-Größe (Experiment-Flag)
    - IBM Product Mapping Integration
    - Document Stats Integration
    - PDF + DOCX Support
    """
    
    def __init__(
        self,
        collection_name: str = "ibm_licenses",
        persist_directory: str = None,
        embedding_model: str = "BAAI/bge-large-en-v1.5",
        use_adaptive_chunking: bool = True,
        ibm_mapping_file: str = "product_mapping.csv"
    ):
        """
        Args:
            collection_name: Name der ChromaDB Collection
            persist_directory: Pfad für persistente Speicherung
            embedding_model: Hugging Face Model-name
            use_adaptive_chunking: True = adaptive Größen, False = fix 400/100
            ibm_mapping_file: Pfad zur IBM Product Mapping-Datei
        """
        self.collection_name = collection_name
        self.use_adaptive_chunking = use_adaptive_chunking
        
        # Default: Speichern neben src/
        if persist_directory is None:
            persist_directory = str(Path(__file__).parent.parent / "data" / "chroma_db")        
        self.persist_directory = persist_directory
        
        # IBM Product Mapping laden
        self.ibm_mapping = load_ibm_product_mapping(ibm_mapping_file)
        logger.info(f"📋 IBM Product Mapping: {len(self.ibm_mapping)} Produkte")

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
                metadata={"description": "IBM Licensing Documents with Product Mapping"}
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
        Reichert Metadaten mit IBM Product Mapping an.
        
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
                
                # Metadaten erweitern: Standard + IBM Mapping
                ibm_metadata = extract_metadata_from_filename(pdf_file.name, self.ibm_mapping)
                
                for chunk in chunks:
                    chunk.metadata['word_count'] = word_count
                    chunk.metadata['chunk_size'] = chunk_size
                    chunk.metadata['overlap'] = overlap
                    chunk.metadata['file_name'] = pdf_file.name
                    # IBM Mapping Metadaten hinzufügen
                    chunk.metadata['manufacturer'] = ibm_metadata['manufacturer']
                    chunk.metadata['product_name'] = ibm_metadata['product_name']
                    chunk.metadata['language'] = ibm_metadata['language']
                    if ibm_metadata.get('license_code') is not None:
                        chunk.metadata['license_code'] = ibm_metadata['license_code']
                
                all_chunks.extend(chunks)
                logger.info(f"  → {len(chunks)} Chunks erstellt ({ibm_metadata['product_name']})")
                
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
                
                # Metadaten erweitern
                ibm_metadata = extract_metadata_from_filename(docx_file.name, self.ibm_mapping)
                
                for chunk in chunks:
                    chunk.metadata['word_count'] = word_count
                    chunk.metadata['chunk_size'] = chunk_size
                    chunk.metadata['overlap'] = overlap
                    chunk.metadata['file_name'] = docx_file.name
                    chunk.metadata['manufacturer'] = ibm_metadata['manufacturer']
                    chunk.metadata['product_name'] = ibm_metadata['product_name']
                    chunk.metadata['language'] = ibm_metadata['language']
                    if ibm_metadata.get('license_code') is not None:
                        chunk.metadata['license_code'] = ibm_metadata['license_code']
                
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
            # Query-Prefix für bessere Retrieval-Qualität (asymmetrische Suche)
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
        metadatas = []
        cleaned_documents = 0
        cleaned_keys = 0
        removed_key_counter = Counter()

        for doc in documents:
            raw_metadata = doc.metadata if isinstance(doc.metadata, dict) else {}
            sanitized_metadata = sanitize_metadata(raw_metadata)
            metadatas.append(sanitized_metadata)

            removed_keys = set(raw_metadata.keys()) - set(sanitized_metadata.keys())
            if removed_keys:
                cleaned_documents += 1
                cleaned_keys += len(removed_keys)
                removed_key_counter.update(removed_keys)

        if cleaned_documents > 0:
            top_removed = ", ".join(
                f"{k}({v})" for k, v in removed_key_counter.most_common(10)
            )
            logger.warning(
                f"⚠️  Metadaten bereinigt: {cleaned_documents}/{len(documents)} Dokumente, "
                f"{cleaned_keys} Keys entfernt (None/verschachtelt/ungültiger Typ). "
                f"Top removed keys: {top_removed}"
            )
        
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
            filter_metadata: Optional: Filter für Metadaten (z.B. {"manufacturer": "IBM"})
            
        Returns:
            Liste von Ergebnissen mit Text, Metadaten, Score
        """
        logger.info(f"🔍 Suche: '{query}'")
        
        # Query-Embedding erstellen (mit Query-Prefix!)
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
        """Gibt erweiterte Statistiken über die Datenbank zurück."""
        count = self.collection.count()
        
        return {
            "collection_name": self.collection_name,
            "total_documents": count,
            "persist_directory": self.persist_directory,
            "embedding_model": str(self.embedding_model),
            "embedding_dimensions": self.embedding_model.get_sentence_embedding_dimension(),
            "adaptive_chunking": self.use_adaptive_chunking,
            "ibm_products_mapped": len(self.ibm_mapping)  # NEU!
        }


# ============================================================================
# MAIN: Build + Test
# ============================================================================

def main():
    """
    Build-Script: Erstellt Vectorstore mit IBM Mapping.
    Baut standardmäßig die FIXED-Baseline-Collection (IBM_FIXED, use_adaptive_chunking=False).
    Für Adaptive-Experimente: collection_name=IBM_ADAPTIVE, use_adaptive_chunking=True.
    """
    from pathlib import Path
    from collection_names import IBM_FIXED
    
    print("=" * 70)
    print("🏗️  BAUE VECTORSTORE MIT IBM PRODUCT MAPPING (FIXED BASELINE)")
    print("=" * 70)
    
    # Pfad zu Dokumenten
    default_data_dir = Path(__file__).parent.parent / "data" / "ibm"
    data_dir = Path(os.getenv("LAS_DATA_DIR", str(default_data_dir)))
    
    # Vectorstore mit FIXED Chunking + IBM Mapping (Baseline)
    vectorstore = LicenseVectorStore(
        collection_name=IBM_FIXED,
        embedding_model="BAAI/bge-large-en-v1.5",
        use_adaptive_chunking=False,  # ← True für Adaptive-Experimente
        ibm_mapping_file="product_mapping.csv"
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
    print(f"Collection:        {stats['collection_name']}")
    print(f"Dokumente:         {stats['total_documents']:,}")
    print(f"IBM Produkte:      {stats['ibm_products_mapped']}")
    print(f"Adaptive Chunking: {stats['adaptive_chunking']}")
    print(f"Gespeichert:       {stats['persist_directory']}")
    print("=" * 70)
    
    # Test-Suche
    print("\n🔍 TEST-SUCHE:")
    print()
    results = vectorstore.search("Was ist Sub-Capacity Lizenzierung?", k=3)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result['score']:.4f}")
        print(f"   Produkt: {result['metadata'].get('product_name', 'N/A')}")
        print(f"   Hersteller: {result['metadata'].get('manufacturer', 'N/A')}")
        print(f"   Quelle: {result['metadata']['source']}")
        print(f"   Text: {result['text'][:200]}...\n")
    
    # Bonus: Test IBM Mapping-Extraktion
    print("\n📋 IBM MAPPING TEST:")
    print()
    test_filenames = [
        "L-CHSG-4QYF8X_en.pdf",
        "L-YRHY-YWPJ3V_de.pdf",
        "Microsoft_Office_365.pdf"
    ]
    
    for filename in test_filenames:
        metadata = extract_metadata_from_filename(filename, vectorstore.ibm_mapping)
        print(f"Datei: {filename}")
        print(f"  → Produkt: {metadata['product_name']}")
        print(f"  → Hersteller: {metadata['manufacturer']}")
        print(f"  → Sprache: {metadata['language']}")
        print()


if __name__ == "__main__":
    main()
