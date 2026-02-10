# LAS/src/test_expert_questions.py
"""
Testet Experten-Fragen gegen Vektordatenbank.
"""

#%%

from vectorstore import LicenseVectorStore
from typing import List, Dict

EXPERT_QUESTIONS = [
    # ===== EINFACHE FRAGEN =====
    {
        "category": "einfach",
        "question": "In welchem Hauptprodukt / Lizenz ist das Produkt WebSphere Application Server als Supporting Product enthalten?",
        "expected_doc": "BundlingSupporting.pdf",  # Vermutung
        "notes": "Supporting Products Liste"
    },
    {
        "category": "einfach",
        "question": "In welchem Hauptprodukt / Lizenz ist das Produkt DB2 als Supporting Product enthalten?",
        "expected_doc": "BundlingSupporting.pdf",  # Vermutung
        "notes": "Supporting Products Liste"
    },
    {
        "category": "einfach",
        "question": "Welche Informationen benötige ich um für ein Produkt den PVU Bedarf unter Full-Capacity zu berechnen?",
        "expected_doc": "IBM_Virtualization_Capacity_August2024.pdf",
        "notes": "PVU Full-Capacity Definition"
    },
    {
        "category": "einfach",
        "question": "Was muss ich beachten und tun um Sub-Capacity Lizenzierung nutzen zu können?",
        "expected_doc": "IBM_Virtualization_Capacity_August2024.pdf",
        "notes": "Sub-Capacity Requirements"
    },
    {
        "category": "einfach",
        "question": "Was ist ein Authorized User?",
        "expected_doc": None,  # Unbekannt - müssen wir sehen
        "notes": "Metrik-Definition"
    },
    {
        "category": "einfach",
        "question": "Was ist ein Virtual Processor Core / VPC?",
        "expected_doc": None,  # Vermutlich in mehreren LIDs
        "notes": "Metrik-Definition"
    },
    
    # ===== SCHWIERIGE FRAGEN =====
    {
        "category": "schwer",
        "question": "Wie wird der RVU Bedarf bei dem Produkt IBM Guardium Data Encryption berechnet?",
        "expected_doc": None,  # Brauchen spezifisches LID
        "notes": "RVU = Resource Value Unit"
    },
    {
        "category": "schwer",
        "question": "Wie wird der AUVU Bedarf bei dem Produkt IBM Verify Identity Governance berechnet?",
        "expected_doc": None,  # Brauchen spezifisches LID
        "notes": "AUVU = Authorized User Value Unit"
    },
    {
        "category": "schwer",
        "question": "Welche Supporting Products habe ich bei dem Product 'IBM Cloud Pak for Business Automation' dabei?",
        "expected_doc": "IBM_CloudPaks.pdf",
        "notes": "Cloud Pak Bundling"
    },
    {
        "category": "schwer",
        "question": "Welche Berechnungen muss ich für den Lizenzbedarf von IBM Cloud Pak for Business Automation durchführen?",
        "expected_doc": "IBM_CloudPaks.pdf",
        "notes": "Cloud Pak Licensing Calculation"
    },
]

def test_questions(questions: List[Dict], k: int = 5):
    """Testet Liste von Fragen."""
    vs = LicenseVectorStore()
    
    results = {
        "einfach": {"correct": 0, "total": 0, "unknown_expected": 0},
        "schwer": {"correct": 0, "total": 0, "unknown_expected": 0},
    }
    
    print("=" * 70)
    print("🧪 EXPERTEN-FRAGEN TEST")
    print("=" * 70)
    
    for i, q in enumerate(questions, 1):
        category = q["category"]
        question = q["question"]
        expected_doc = q.get("expected_doc")
        notes = q.get("notes", "")
        
        print(f"\n{'='*70}")
        print(f"Frage {i}/{len(questions)} ({category.upper()})")
        print(f"{'='*70}")
        print(f"Q: {question}")
        if notes:
            print(f"   ({notes})")
        
        if expected_doc:
            print(f"\nErwartet: {expected_doc}")
        else:
            print(f"\nErwartet: UNBEKANNT (müssen wir sehen)")
        
        print("-" * 70)
        
        # Suche
        search_results = vs.search(question, k=k)
        
        if not search_results:
            print("❌ KEINE ERGEBNISSE")
            results[category]["total"] += 1
            continue
        
        # Beste Ergebnis
        best = search_results[0]        
        found_doc = best['metadata'].get('file_name') or best['metadata']['source'].split('/')[-1]
        score = best['score']
        
        print(f"Gefunden: {found_doc} (Score: {score:.4f})")
        
        # Bewertung
        results[category]["total"] += 1
        
        if expected_doc is None:
            results[category]["unknown_expected"] += 1
            print("⚠️  UNBEKANNT (kein Expected-Doc definiert)")
        elif found_doc == expected_doc:
            results[category]["correct"] += 1
            print("✅ KORREKT")
        else:
            print(f"❌ FALSCH (erwartet: {expected_doc})")
        
        # Top-K anzeigen
        print(f"\nTop-{k} Ergebnisse:")
        for j, r in enumerate(search_results, 1):
            doc_name = r['metadata'].get('file_name') or r['metadata']['source'].split('/')[-1]
            print(f"  {j}. {doc_name} (Score: {r['score']:.4f})")
            if 'page' in r['metadata']:
                print(f"     Seite: {r['metadata']['page']}")
            # Ersten 100 Zeichen anzeigen
            text_preview = r['text'][:100].replace('\n', ' ')
            print(f"     Text: {text_preview}...")
    
    # Gesamt-Statistik
    print("\n" + "=" * 70)
    print("📊 ERGEBNISSE")
    print("=" * 70)
    
    for category in ["einfach", "schwer"]:
        total = results[category]["total"]
        if total > 0:
            correct = results[category]["correct"]
            unknown = results[category]["unknown_expected"]
            testable = total - unknown
            
            if testable > 0:
                percentage = (correct / testable) * 100
                print(f"{category.upper():10}: {correct}/{testable} testbar = {percentage:.1f}%")
            else:
                print(f"{category.upper():10}: 0/{total} testbar (alle unbekannt)")
            
            if unknown > 0:
                print(f"           ({unknown} Fragen ohne Expected-Doc)")
    
    print("=" * 70)

if __name__ == "__main__":
    test_questions(EXPERT_QUESTIONS, k=5)