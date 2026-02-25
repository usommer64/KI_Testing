#!/usr/bin/env python3
"""
Extrahiert Produktnamen aus IBM Lizenzdokumenten (erste Zeile, erste Seite)
Erstellt product_mapping.csv für Metadata-Enrichment
"""

from pathlib import Path
import PyPDF2
import re
import csv

def extract_ibm_product_name(pdf_path: Path) -> dict:
    """
    Extrahiert Produktname aus erster Zeile der ersten Seite
    
    Returns:
        dict mit license_code, product_name, filename
    """
    filename = pdf_path.name
    
    # Nur IBM Docs (Pattern: L-XXXX-XXXXXX_xx.pdf)
    ibm_pattern = r'(L-[A-Z]{4}-[A-Z0-9]{6})_([a-z]{2})\.pdf'
    match = re.match(ibm_pattern, filename, re.IGNORECASE)
    
    if not match:
        return None  # Nicht IBM oder falsches Format
    
    license_code = match.group(1)
    language = match.group(2)
    
    try:
        # PDF öffnen
        with open(pdf_path, 'rb') as f:
            pdf = PyPDF2.PdfReader(f)
            
            if len(pdf.pages) == 0:
                print(f"⚠️  {filename}: Keine Seiten gefunden")
                return None
            
            # Erste Seite
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            if not text:
                print(f"⚠️  {filename}: Kein Text extrahierbar")
                return None
            
            # Erste nicht-leere Zeile
            lines = text.split('\n')
            product_name = None
            
            for line in lines:
                line = line.strip()
                if line:  # Erste nicht-leere Zeile
                    product_name = line
                    break
            
            if not product_name:
                print(f"⚠️  {filename}: Keine Produktname gefunden")
                return None
            
            # Cleanup: Entferne Part Numbers in Klammern am Ende
            # "IBM WebSphere Application Server V8.5.5.26 (5724-J08)"
            # → "IBM WebSphere Application Server V8.5.5.26"
            product_name = re.sub(r'\s*\([^\)]+\)\s*$', '', product_name)
            
            # Cleanup: Entferne Versionsnummern? (optional)
            # Kommentiere aus wenn du Versionen behalten willst
            # product_name = re.sub(r'\s+V?\d+\.\d+.*$', '', product_name)
            
            return {
                'license_code': license_code,
                'product_name': product_name,
                'language': language,
                'filename': filename
            }
    
    except Exception as e:
        print(f"❌ Fehler bei {filename}: {e}")
        return None


def main():
    """Hauptfunktion: Verarbeitet alle IBM PDFs"""
    
    # Pfad zu Dokumenten
    data_dir = Path(__file__).parent.parent / "data"
    
    print("=" * 70)
    print("📄 EXTRAHIERE IBM PRODUKTNAMEN")
    print("=" * 70)
    print(f"Verzeichnis: {data_dir}")
    print()
    
    # Finde alle PDFs
    pdf_files = list(data_dir.glob("L-*.pdf")) + list(data_dir.glob("L-*.PDF"))
    
    print(f"Gefunden: {len(pdf_files)} IBM Lizenzdokumente")
    print()
    
    # Extrahiere Produktnamen
    results = []
    for pdf_file in sorted(pdf_files):
        print(f"📄 {pdf_file.name}...", end=" ")
        
        data = extract_ibm_product_name(pdf_file)
        
        if data:
            print(f"✅ {data['product_name'][:60]}")
            results.append(data)
        else:
            print("❌ Übersprungen")
    
    # CSV erstellen
    if results:
        csv_path = Path(__file__).parent / "product_mapping.csv"
        
        print()
        print("=" * 70)
        print(f"💾 Speichere {len(results)} Einträge in: {csv_path}")
        print("=" * 70)
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['license_code', 'product_name', 'language', 'filename'])
            writer.writeheader()
            writer.writerows(results)
        
        print("✅ Fertig!")
        print()
        
        # Zeige Beispiele
        print("Beispiele:")
        print("-" * 70)
        for i, row in enumerate(results[:5], 1):
            print(f"{i}. {row['license_code']:20} | {row['product_name'][:45]}")
        if len(results) > 5:
            print(f"... und {len(results) - 5} weitere")
    else:
        print("\n⚠️  Keine Daten extrahiert")


if __name__ == "__main__":
    main()