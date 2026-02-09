"""
Analysiert alle PDFs im data/ Ordner und erstellt eine CSV mit Statistiken.
"""

import os
import PyPDF2
import csv
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_pdf(pdf_path):
    """
    Analysiert ein PDF und extrahiert Statistiken.
    
    Returns:
        dict mit Metriken oder None bei Fehler
    """
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            # Text extrahieren
            full_text = ""
            for page in reader.pages:
                try:
                    full_text += page.extract_text() + "\n"
                except Exception as e:
                    logger.warning(f"Fehler bei Seite in {pdf_path}: {e}")
                    continue
            
            # Statistiken berechnen
            words = full_text.split()
            word_count = len(words)
            char_count = len(full_text)
            
            # Absätze (durch doppelte Zeilenumbrüche getrennt)
            paragraphs = [p for p in full_text.split('\n\n') if p.strip()]
            paragraph_count = len(paragraphs)
            
            # Sätze (grobe Schätzung via Punkte)
            sentence_count = full_text.count('.') + full_text.count('!') + full_text.count('?')
            
            # Seiten
            page_count = len(reader.pages)
            
            # Dateigröße
            file_size_bytes = os.path.getsize(pdf_path)
            file_size_kb = file_size_bytes / 1024
            
            # Durchschnittswerte
            words_per_page = word_count / page_count if page_count > 0 else 0
            chars_per_word = char_count / word_count if word_count > 0 else 0
            words_per_paragraph = word_count / paragraph_count if paragraph_count > 0 else 0
            
            return {
                'filename': os.path.basename(pdf_path),
                'file_size_kb': round(file_size_kb, 1),
                'pages': page_count,
                'words': word_count,
                'characters': char_count,
                'paragraphs': paragraph_count,
                'sentences': sentence_count,
                'words_per_page': round(words_per_page, 1),
                'chars_per_word': round(chars_per_word, 1),
                'words_per_paragraph': round(words_per_paragraph, 1),
            }
    
    except Exception as e:
        logger.error(f"❌ Fehler bei {pdf_path}: {e}")
        return None


def analyze_all_pdfs(data_dir):
    """Analysiert alle PDFs in einem Verzeichnis."""
    
    pdf_files = list(Path(data_dir).glob('*.pdf'))
    logger.info(f"📊 Analysiere {len(pdf_files)} PDFs...")
    
    results = []
    
    for pdf_path in sorted(pdf_files):
        logger.info(f"📄 {pdf_path.name}...")
        stats = analyze_pdf(pdf_path)
        
        if stats:
            results.append(stats)
    
    return results


def save_to_csv(results, output_path):
    """Speichert Ergebnisse als CSV."""
    
    if not results:
        logger.error("Keine Ergebnisse zum Speichern!")
        return
    
    # Spalten aus erstem Ergebnis
    fieldnames = results[0].keys()
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    logger.info(f"✅ Gespeichert: {output_path}")


def print_summary(results):
    """Gibt Zusammenfassung aus."""
    
    if not results:
        return
    
    total_words = sum(r['words'] for r in results)
    total_pages = sum(r['pages'] for r in results)
    
    print("\n" + "="*70)
    print("📊 ZUSAMMENFASSUNG")
    print("="*70)
    print(f"Dokumente:     {len(results)}")
    print(f"Gesamt Seiten: {total_pages:,}")
    print(f"Gesamt Wörter: {total_words:,}")
    print(f"Ø Wörter/Doc:  {total_words/len(results):,.0f}")
    print()
    
    # Sortiert nach Wörtern
    print("Top 5 längste Dokumente (nach Wörtern):")
    sorted_results = sorted(results, key=lambda x: x['words'], reverse=True)
    for r in sorted_results[:5]:
        print(f"  {r['filename']:40s} {r['words']:>6,} Wörter")
    
    print()
    print("Top 5 kürzeste Dokumente (nach Wörtern):")
    for r in sorted_results[-5:]:
        print(f"  {r['filename']:40s} {r['words']:>6,} Wörter")
    
    print("="*70)


if __name__ == "__main__":
    # Pfade anpassen
    DATA_DIR = "/workspaces/KI_Testing/.devcontainer/LAS/data"
    OUTPUT_CSV = "/workspaces/KI_Testing/.devcontainer/LAS/data/document_stats.csv"
    
    # Analysieren
    results = analyze_all_pdfs(DATA_DIR)
    
    # Zusammenfassung ausgeben
    print_summary(results)
    
    # CSV speichern
    save_to_csv(results, OUTPUT_CSV)
    
    print(f"\n✅ Fertig! CSV gespeichert: {OUTPUT_CSV}")
    print(f"   Öffnen mit: cat {OUTPUT_CSV}")