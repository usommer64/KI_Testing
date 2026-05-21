#!/usr/bin/env python3
"""
Experten-Fragen Test mit Ground Truth - Phase 1

Vendor-Filter:
  Per Umgebungsvariable: LAS_VENDOR=IBM|Microsoft|All  (Default: IBM)
  Per CLI-Argument:      --vendor IBM|Microsoft|All
"""

import argparse
import logging
import os
import re
import json
from pathlib import Path
from vectorstore_IBM_Mapping import LicenseVectorStore
from collection_names import IBM_FIXED

#---temporäres debuging
import inspect
print("LicenseVectorStore object:", LicenseVectorStore)
print("Defined in:", inspect.getfile(LicenseVectorStore))
print("Signature:", inspect.signature(LicenseVectorStore))
#---temporäres debuging ende

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

def expand_query(question: str) -> str:
    q = question
    q_l = question.lower()

    # PVU / Capacity / Sub-Capacity / Virtualization (vendor-agnostisch)
    if (
        re.search(r"\bpvu\b", q_l)
        or "full-capacity" in q_l or "full capacity" in q_l
        or "sub-capacity" in q_l or "sub capacity" in q_l
        or "virtualization" in q_l or "virtualisierung" in q_l
        or "ilmt" in q_l
    ):
        q += (
            " Processor Value Unit PVU"
            " full capacity sub-capacity virtualization capacity"
            " eligibility requirements eligible virtualization technology operating system"
            " approved metering tool ILMT BigFix Inventory"
            " monitor meter peak"
        )

    # RVU
    if re.search(r"\brvu\b", q_l) or "resource value unit" in q_l:
        q += (
            " Resource Value Unit RVU"
            " conversion table calculate required entitlements"
        )

    # UVU (falls relevant)
    if re.search(r"\buvu\b", q_l) or "user value unit" in q_l:
        q += (
            " User Value Unit UVU"
            " authorized user"
        )

    return q

# ======================================================================
# QUESTIONS FILE (JSON)
# ======================================================================

DEFAULT_QUESTIONS_FILE = Path(__file__).parent / "questions" / "ibm_expert_questions.json"

def load_questions_from_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Questions JSON must be a list")

    questions = {}
    for item in data:
        q_id = item["id"]

        # prefer explicit "question", else DE, else EN
        q_text = (item.get("question") or item.get("question_de") or item.get("question_en") or "").strip()
        if not q_text:
            raise ValueError(f"Question text missing for {q_id}")

        questions[q_id] = {
            "vendor": item.get("vendor", "IBM"),
            "difficulty": item.get("difficulty", "MITTEL"),
            "question": q_text,
            "primary_doc": item["expected_doc"],
            "alternative_docs": item.get("alternative_docs", []),
            "pages": item.get("expected_pages", []),
            "section": item.get("expected_section", ""),
            "reason": item.get("reason", ""),
            # optional future use:
            # "expected_answer_snippet": item.get("expected_answer_snippet"),
        }

    return questions

# Load questions from JSON (default IBM set)
QUESTIONS_FILE = Path(os.environ.get("LAS_QUESTIONS_FILE", str(DEFAULT_QUESTIONS_FILE)))
EXPERT_QUESTIONS = load_questions_from_json(QUESTIONS_FILE)

def test_questions(vendor_filter="IBM", only_ids=None):
    """Führt alle Test-Fragen aus und bewertet Ergebnisse.

    Args:
        vendor_filter: "IBM", "Microsoft" oder "All" (default: "IBM")
        only_ids: Optionale Liste von Fragen-IDs (z. B. ["IBM-009", "IBM-012"])
    """
    only_ids = list(dict.fromkeys(only_ids or []))

    # Fragen nach Vendor filtern
    if vendor_filter == "All":
        filtered_questions = EXPERT_QUESTIONS
    else:
        filtered_questions = {
            k: v for k, v in EXPERT_QUESTIONS.items()
            if v["vendor"] == vendor_filter
        }

    # Optional auf explizite Fragen-IDs einschränken
    if only_ids:
        only_ids_set = set(only_ids)
        filtered_questions = {
            k: v for k, v in filtered_questions.items()
            if k in only_ids_set
        }

    n_filtered = len(filtered_questions)
    n_total = len(EXPERT_QUESTIONS)
    only_suffix = f", only={','.join(only_ids)}" if only_ids else ""

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

    print("=" * 70)
    print(f"🧪 EXPERTEN-FRAGEN TEST - PHASE 1 ({n_filtered} Fragen{only_suffix})")
    if vendor_filter == "All":
        print(f"   Vendor-Filter: Alle ({n_filtered} Fragen)")
    else:
        print(f"   Vendor-Filter: {vendor_filter} ({n_filtered}/{n_total} Fragen nach Filter)")
    if only_ids:
        print(f"   Only-Filter: {', '.join(only_ids)}")
    print("=" * 70)
    print()

    if n_filtered == 0:
        print("⚠️  Keine Fragen nach den gesetzten Filtern ausgewählt.")
        return stats

    # Initialisiere VectorStore (FIXED EXPERIMENT)
    vs = LicenseVectorStore(
        collection_name=IBM_FIXED,
        embedding_model="BAAI/bge-large-en-v1.5",
        use_adaptive_chunking=False
    )

    # Teste jede Frage
    for q_id, q_data in filtered_questions.items():
        stats["total"] += 1

        vendor = q_data["vendor"]
        difficulty = q_data["difficulty"]
        question = q_data["question"]
        expected_doc = q_data["primary_doc"]
        alternative_docs = q_data.get("alternative_docs", [])

        print("=" * 70)
        print(f"Frage {stats['total']}/{n_filtered} ({vendor} - {difficulty})")
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

        # Suche durchführen - Reranking optional per Env
        rerank = os.environ.get("LAS_RERANK", "0") == "1"
        rerank_top_n = int(os.environ.get("LAS_RERANK_TOP_N", "30"))
        rerank_model = os.environ.get("LAS_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

        # Für die Bewertung wollen wir IMMER Top-5 zurückbekommen:
        k_eval = 5

        # Query-Expansion (vendor-/question-agnostisch)
        question_to_search = expand_query(question)

        results = vs.search(
            question_to_search,
            k=k_eval,
            rerank=rerank,
            rerank_top_n=rerank_top_n,
            rerank_model=rerank_model,
            rerank_query=question,
        )
      # DEBUG: Optional dense-only Top-100 OHNE Rerank (LAS_DEBUG_DENSE_TOP100=1)
        debug_dense_top100 = os.environ.get("LAS_DEBUG_DENSE_TOP100", "0") == "1"
        debug_results = None
        if debug_dense_top100:
            debug_results = vs.search(question_to_search, k=100, rerank=False)

        # Bewertung
        found_at = None
        all_valid_docs = [expected_doc] + alternative_docs

        for i, result in enumerate(results, 1):
            source = result["metadata"].get("source", "")
            doc_name = Path(source).name if source else "UNKNOWN"

            # Spezialfall: Microsoft Product Terms (für spätere Nutzung)
            if expected_doc == "Product Terms":
                if "Product Terms" in doc_name:
                    found_at = i
                    break
            # Normalfall: Exakter Dateiname
            elif doc_name in all_valid_docs:
                found_at = i
                break

        # DEBUG: Prüfen, ob erwartetes Doc irgendwo in den (evtl. >5) Ergebnissen vorkommt
        if debug_dense_top100 and debug_results is not None:
            hits = []
            for j, r in enumerate(debug_results, 1):
                source = r["metadata"].get("source", "")
                doc_name = Path(source).name if source else "UNKNOWN"
                if doc_name == expected_doc:
                    page = r["metadata"].get("page", "?")
                    preview = (r.get("text", "") or "").replace("\n", " ")[:160]
                    hits.append((j, page, preview))

            print(
                f"\nDEBUG (dense-only): '{expected_doc}' Treffer in Top-{len(debug_results)}: "
                f"{[(pos, page) for (pos, page, _) in hits] if hits else 'NICHT ENTHALTEN'}\n"
            )

            # Detailausgabe pro Treffer (Position, Seite, Text-Preview)
            for pos, page, preview in hits:
                print(f"   - Hit @ {pos:>3} | Seite {page}: {preview}...")
            print()
            
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
    
    # Vendor-Filter: CLI-Argument hat Vorrang vor Umgebungsvariable
    parser = argparse.ArgumentParser(description="Experten-Fragen Test mit Ground Truth")
    parser.add_argument(
        "--vendor",
        default=os.environ.get("LAS_VENDOR", "IBM"),
        choices=["IBM", "Microsoft", "All"],
        help="Vendor-Filter für Testfragen (default: IBM, oder LAS_VENDOR env var)"
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Nur bestimmte Fragen-IDs ausführen (mehrfach oder CSV, z.B. --only IBM-009 --only IBM-012 oder --only IBM-009,IBM-012)"
    )
    parser.add_argument(
        "--list-ids",
        action="store_true",
        help="Alle verfügbaren Fragen-IDs anzeigen und beenden"
    )
    args = parser.parse_args()

    if args.list_ids:
        for q_id in sorted(EXPERT_QUESTIONS):
            print(q_id)
        sys.exit(0)

    only_ids = []
    for item in args.only:
        only_ids.extend([q_id.strip() for q_id in item.split(",") if q_id.strip()])
    only_ids = list(dict.fromkeys(only_ids))

    if only_ids:
        missing_ids = [q_id for q_id in only_ids if q_id not in EXPERT_QUESTIONS]
        if missing_ids:
            print(f"❌ Unbekannte Fragen-IDs: {', '.join(missing_ids)}")
            print("Nutze --list-ids für alle verfügbaren IDs.")
            sys.exit(2)

    vendor_filter = args.vendor
    
    # Test durchführen
    stats = test_questions(vendor_filter=vendor_filter, only_ids=only_ids)
    
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
            "vendor_filter": vendor_filter,
            "vendors": [vendor_filter] if vendor_filter != "All" else sorted({v.get("vendor") for v in EXPERT_QUESTIONS.values() if v.get("vendor")}),
            "only_ids": only_ids,
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
