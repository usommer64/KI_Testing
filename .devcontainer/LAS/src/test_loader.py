"""
Test-Script für den Document Loader
"""
#%%
from pathlib import Path
from loader import LicenseDocumentLoader


def test_loader():
    """Testet den Document Loader mit IBM-Dokumenten"""
    
    # Pfad zu den Dokumenten
    data_dir = Path(__file__).parent.parent / "data" 
    print("=" * 70)
    print("🧪 TEST: Document Loader")
    print("=" * 70)
    print(f"\n📂 Verzeichnis: {data_dir}")
    print(f"📂 Existiert: {data_dir.exists()}")
    
    # Dateien auflisten
    if data_dir.exists():
        files = list(data_dir.rglob("*.*"))
        print(f"\n📄 Gefundene Dateien ({len(files)}):")
        for f in files:
            size_kb = f.stat().st_size / 1024
            print(f"  - {f.name:40s} ({size_kb:6.1f} KB)")
    
    print("\n" + "-" * 70)
    
    # Loader erstellen
    loader = LicenseDocumentLoader(
        chunk_size=1000,
        chunk_overlap=200
    )
    
    # Dokumente laden
    print("\n📚 Lade Dokumente...")
    documents = loader.load_directory(data_dir)
    print(f"✅ {len(documents)} Dokumente geladen")
    
    # Nach Dateityp gruppieren
    by_type = {}
    for doc in documents:
        file_type = doc.metadata.get("file_type", "unknown")
        by_type[file_type] = by_type.get(file_type, 0) + 1
    
    print("\n📊 Dokumente nach Typ:")
    for file_type, count in by_type.items():
        print(f"  - {file_type:10s}: {count:3d}")
    
    # Chunking
    print("\n✂️  Splitte Dokumente in Chunks...")
    chunks = loader.split_documents(documents)
    print(f"✅ {len(chunks)} Chunks erstellt")
    
    # Statistiken
    total_chars = sum(len(chunk.page_content) for chunk in chunks)
    avg_chunk_size = total_chars / len(chunks) if chunks else 0
    
    print("\n📊 Statistiken:")
    print(f"  - Dokumente:        {len(documents)}")
    print(f"  - Chunks:           {len(chunks)}")
    print(f"  - Zeichen gesamt:   {total_chars:,}")
    print(f"  - Ø Chunk-Größe:    {avg_chunk_size:.0f} Zeichen")
    
    # Beispiele zeigen
    print("\n" + "=" * 70)
    print("📄 BEISPIEL-CHUNKS")
    print("=" * 70)
    
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"\n--- Chunk {i} ---")
        print(f"Quelle: {chunk.metadata.get('file_name', 'unknown')}")
        print(f"Typ: {chunk.metadata.get('file_type', 'unknown')}")
        print(f"Seite: {chunk.metadata.get('page', 'N/A')}")
        print(f"Länge: {len(chunk.page_content)} Zeichen")
        print(f"\nInhalt:\n{chunk.page_content[:300]}...")
    
    print("\n" + "=" * 70)
    print("✅ TEST ABGESCHLOSSEN")
    print("=" * 70)


if __name__ == "__main__":
    test_loader()
