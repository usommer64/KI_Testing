#!/usr/bin/env python3
"""
Experten-Fragen Test mit Ground Truth - Phase 1
"""

import logging
from pathlib import Path
from vectorstore import LicenseVectorStore

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

# ======================================================================
# TEST-FRAGEN MIT GROUND TRUTH
# ======================================================================

EXPERT_QUESTIONS = {
    # ===== IBM (3 Fragen) =====
    "ibm_1": {
        "vendor": "IBM",
        "difficulty": "EINFACH",
        "question": "Welche Produkte sind im Produkt WebSphere Application Server als Supporting Product enthalten?",
        "primary_doc": "L-YRHY-YWPJ3V_de.pdf",
        "alternative_docs": [],
        "pages": [2, 3],
        "section": "Supporting Products Liste",
        "reason": "Auf den Seiten 2 und 3 des Dokuments sind die Supporting Products aufgelistet",
    },
    
    "ibm_2": {
        "vendor": "IBM",
        "difficulty": "MITTEL",
        "question": "Welche Informationen benötige ich um für ein Produkt den PVU Bedarf unter Full-Capacity zu berechnen?",
        "primary_doc": "IBM_Virtualization_Capacity_August2024.pdf",
        "alternative_docs": [],
        "pages": [5, 6],
        "section": "Sub Capacity Requirements",
        "reason": "Prinzip der Sub Capacity Zählung und die 4 Voraussetzungen, die erfüllt sein müssen, werden dargestellt",
    },
    
    "ibm_3": {
        "vendor": "IBM",
        "difficulty": "SCHWER",
        "question": "Wie wird der RVU Bedarf bei dem Produkt IBM Content Manager Enterprise Edition berechnet?",
        "primary_doc": "IBM-License-Measurement-Methodology-IBM-Content-Manager-Enterprise-Edition.pdf",
        "alternative_docs": [],
        "pages": [4, 11, 12],
        "section": "RVU Calculation",
        "reason": "Auf Seite 4 wird die RVU genannt, die für dieses Programm gilt. Auf Seite 11 und 12 werden die relevanten Umrechnungsfaktoren genannt",
    },
    
    # ===== MICROSOFT (4 Fragen) =====
    "ms_1": {
        "vendor": "Microsoft",
        "difficulty": "EINFACH",
        "question": "In welchen Fällen muss der Zugriff auf Dynamics 365 nicht mit einer Client Access CAL pro User (User CAL) lizenziert werden?",
        "primary_doc": "Microsoft_Multiplexing Licensing Guidance.PDF",
        "alternative_docs": [],
        "pages": [5],
        "section": "Restricted vs Unrestricted Tables",
        "reason": "Hier wird der Unterschied zwischen restricted und unrestricted Tables erklärt",
    },
    
    "ms_2": {
        "vendor": "Microsoft",
        "difficulty": "EINFACH",
        "question": "Welches Betriebssystem gilt nicht als Qualifizierendes Betriebssystem für Windows 11 Upgrade Lizenzen?",
        "primary_doc": "Microsoft_Windows 11 Qualifying OS Licensing Guidance.PDF",
        "alternative_docs": [],
        "pages": [3],
        "section": "Qualifying OS Table",
        "reason": "Hier wird eine Tabelle gezeigt, in der es für Windows Embedded operating systems KEIN Kreuzchen gibt",
    },
    
    "ms_3": {
        "vendor": "Microsoft",
        "difficulty": "MITTEL",
        "question": "Was ist die Voraussetzung dafür, dass ein Kunde Step-Up Lizenzen erwerben kann?",
        "primary_doc": "Microsoft_Step-Up Licenses Licensing Guidance.PDF",
        "alternative_docs": [],
        "pages": [2],
        "section": "Prerequisites",
        "reason": "Hier wird die Voraussetzung genannt (aktive Software Assurance)",
    },
    
    "ms_4": {
        "vendor": "Microsoft",
        "difficulty": "SCHWER",
        "question": "Wie lange ist eine Lizenz nach ihrer Zuweisung an ein Gerät oder Nutzer mindestens an dieses Gerät oder diesen Nutzer gebunden?",
        "primary_doc": "Product Terms",  # Flexibel - alle Product Terms Docs akzeptieren
        "alternative_docs": [],
        "pages": [],  # Unbekannt - in Universal License Terms Abschnitt
        "section": "Universal License Terms / For All Software / License Assignment and Reassignment",
        "reason": "Hier wird der Zeitraum genannt (90 Tage)",
    },
}


def test_questions():
    """Führt alle Test-Fragen aus und bewertet Ergebnisse"""
    
    print("=" * 70)
    print("🧪 EXPERTEN-FRAGEN TEST - PHASE 1 (7 Fragen)")
    print("=" * 70)
    print()
    
    # Initialisiere VectorStore (FIXED EXPERIMENT)
    vs = LicenseVectorStore(
        collection_name="ibm_licenses_fixed",
        embedding_model="BAAI/bge-large-en-v1.5",
        use_adaptive_chunking=False
    )
    
    # Statistiken
    stats = {
        "total": 0,
        "top1_correct": 0,  # Richtiges Doc auf Platz 1
        "top3_correct": 0,  # Richtiges Doc in Top-3
        "top5_correct": 0,  # Richtiges Doc in Top-5
        "not_found": 0,     # Richtiges Doc nicht in Top-5
        "by_vendor": {},    # Statistik pro Vendor
        "by_difficulty": {} # Statistik pro Schwierigkeit
    }
    
    # Teste jede Frage
    for q_id, q_data in EXPERT_QUESTIONS.items():
        stats["total"] += 1
        
        vendor = q_data["vendor"]
        difficulty = q_data["difficulty"]
        question = q_data["question"]
        expected_doc = q_data["primary_doc"]
        alternative_docs = q_data.get("alternative_docs", [])
        
        print("=" * 70)
        print(f"Frage {stats['total']}/{len(EXPERT_QUESTIONS)} ({vendor} - {difficulty})")
        print("=" * 70)
        print(f"Q: {question}")
        print()
        print(f"Erwartet: {expected_doc}")
        if alternative_docs:
            print(f"Auch ok: {', '.join(alternative_docs)}")
        if q_data.get("pages"):
            print(f"Seiten: {q_data['pages']}")
        if q_data.get("section"):
            print(f"Abschnitt: {q_data['section']}")
        if q_data.get("reason"):
            print(f"Grund: {q_data['reason']}")
        print("-" * 70)
        
        # Suche durchführen
        results = vs.search(question, k=5)
        
        # Bewertung
        found_at = None
        all_valid_docs = [expected_doc] + alternative_docs
        
        for i, result in enumerate(results, 1):
            # FIX: Extrahiere Dateinamen aus source (Fixed-Collection hat kein file_name)
            source = result["metadata"].get("source", "")
            doc_name = Path(source).name if source else "UNKNOWN"
            
            # Spezialfall: Microsoft Product Terms (akzeptiere alle Dateien die "Product Terms" enthalten)
            if expected_doc == "Product Terms":
                if "Product Terms" in doc_name:
                    found_at = i
                    break
            # Normalfall: Exakter Dateiname
            elif doc_name in all_valid_docs:
                found_at = i
                break
        
        # Statistiken aktualisieren
        if found_at == 1:
            stats["top1_correct"] += 1
            stats["top3_correct"] += 1
            stats["top5_correct"] += 1
            print(f"✅ PERFEKT - Auf Platz 1!")
        elif found_at and found_at <= 3:
            stats["top3_correct"] += 1
            stats["top5_correct"] += 1
            print(f"⚠️  OK - Auf Platz {found_at}")
        elif found_at and found_at <= 5:
            stats["top5_correct"] += 1
            print(f"⚠️  GEFUNDEN - Auf Platz {found_at}")
        else:
            stats["not_found"] += 1
            print(f"❌ NICHT GEFUNDEN in Top-5")
        
        print()
        print("Top-5 Ergebnisse:")
        for i, result in enumerate(results, 1):
            # FIX: Extrahiere Dateinamen aus source (Fixed-Collection hat kein file_name)
            source = result["metadata"].get("source", "")
            doc_name = Path(source).name if source else "UNKNOWN"
            page = result["metadata"].get("page", "?")
    
            # FIX: Flexibler Score-Zugriff
            score = result.get("distance") or result.get("score") or result.get("similarity", 0.0)
    
            # Marker für richtiges Dokument
            is_correct = False
            if expected_doc == "Product Terms":
                is_correct = "Product Terms" in doc_name
            else:
                is_correct = doc_name in all_valid_docs
    
            marker = "👉" if is_correct else "  "
            print(f"{marker} {i}. {doc_name} (Seite: {page}, Score: {score:.4f})")
             
            # Zeige Preview des Texts (erste 150 Zeichen)
            text_preview = result.get("text", "")[:150].replace("\n", " ")
            print(f"      Preview: {text_preview}...")
        
        
        # Vendor-Statistik
        if vendor not in stats["by_vendor"]:
            stats["by_vendor"][vendor] = {"total": 0, "top1": 0, "top3": 0, "top5": 0}
        stats["by_vendor"][vendor]["total"] += 1
        if found_at == 1:
            stats["by_vendor"][vendor]["top1"] += 1
        if found_at and found_at <= 3:
            stats["by_vendor"][vendor]["top3"] += 1
        if found_at and found_at <= 5:
            stats["by_vendor"][vendor]["top5"] += 1
        
        # Difficulty-Statistik
        if difficulty not in stats["by_difficulty"]:
            stats["by_difficulty"][difficulty] = {"total": 0, "top1": 0, "top3": 0, "top5": 0}
        stats["by_difficulty"][difficulty]["total"] += 1
        if found_at == 1:
            stats["by_difficulty"][difficulty]["top1"] += 1
        if found_at and found_at <= 3:
            stats["by_difficulty"][difficulty]["top3"] += 1
        if found_at and found_at <= 5:
            stats["by_difficulty"][difficulty]["top5"] += 1
    
    # ===== ZUSAMMENFASSUNG =====
    print("=" * 70)
    print("📊 GESAMT-ERGEBNISSE")
    print("=" * 70)
    
    total = stats["total"]
    print(f"Gesamt:        {total} Fragen")
    print(f"Top-1 korrekt: {stats['top1_correct']}/{total} = {stats['top1_correct']/total*100:.1f}%")
    print(f"Top-3 korrekt: {stats['top3_correct']}/{total} = {stats['top3_correct']/total*100:.1f}%")
    print(f"Top-5 korrekt: {stats['top5_correct']}/{total} = {stats['top5_correct']/total*100:.1f}%")
    print()
    
    # Pro Vendor
    print("=" * 70)
    print("📊 ERGEBNISSE PRO VENDOR")
    print("=" * 70)
    for vendor, data in sorted(stats["by_vendor"].items()):
        t = data["total"]
        t1 = data["top1"]
        t3 = data["top3"]
        t5 = data["top5"]
        print(f"{vendor:12} | Total: {t} | Top-1: {t1}/{t} ({t1/t*100:.0f}%) | Top-3: {t3}/{t} ({t3/t*100:.0f}%) | Top-5: {t5}/{t} ({t5/t*100:.0f}%)")
    print()
    
    # Pro Difficulty
    print("=" * 70)
    print("📊 ERGEBNISSE PRO SCHWIERIGKEIT")
    print("=" * 70)
    for diff, data in sorted(stats["by_difficulty"].items()):
        t = data["total"]
        t1 = data["top1"]
        t3 = data["top3"]
        t5 = data["top5"]
        print(f"{diff:12} | Total: {t} | Top-1: {t1}/{t} ({t1/t*100:.0f}%) | Top-3: {t3}/{t} ({t3/t*100:.0f}%) | Top-5: {t5}/{t} ({t5/t*100:.0f}%)")
    print()
    
    return stats


if __name__ == "__main__":
    import sys
    
    # Test durchführen
    stats = test_questions()
    
    # Experiment tracken (optional - wenn experiment_tracker.py existiert)
    try:
        from experiment_tracker import ExperimentTracker
        
        print("=" * 70)
        print("💾 EXPERIMENT SPEICHERN")
        print("=" * 70)
        
        experiment_name = input("\nExperiment-Name (z.B. 'baseline_phase1'): ").strip()
        if not experiment_name:
            experiment_name = "baseline_phase1"
        
        notes = input("Notizen (optional): ").strip()
        
        # Config
        config = {
            "chunk_size": "adaptive",
            "model": "BAAI/bge-large-en-v1.5",
            "k": 5,
            "vendors": ["IBM", "Microsoft"],
            "phase": "1",
            "num_docs": "~80 (IBM + Microsoft + Red Hat + SUSE)"
        }
        
        tracker = ExperimentTracker()
        tracker.log_experiment(
            experiment_name=experiment_name,
            config=config,
            results=stats,
            notes=notes
        )
        
        # Zeige bisherige Experimente
        print("\n")
        tracker.compare_experiments()
        
    except ImportError:
        print("\n⚠️  experiment_tracker.py nicht gefunden - Experiment nicht gespeichert")
        print("   (Kein Problem - kannst du später nachholen)")