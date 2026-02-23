#!/usr/bin/env python3
"""
Experiment Tracking für RAG-Optimierung
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

class ExperimentTracker:
    """Trackt Experimente und deren Ergebnisse"""
    
    def __init__(self, log_dir: str = "../experiments"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
    def log_experiment(
        self,
        experiment_name: str,
        config: Dict[str, Any],
        results: Dict[str, Any],
        notes: str = ""
    ):
        """
        Loggt ein Experiment
        
        Args:
            experiment_name: Name (z.B. "baseline", "adaptive_chunking_v1")
            config: Konfigurations-Parameter (chunk_size, model, etc.)
            results: Test-Ergebnisse (top1_correct, top3_correct, etc.)
            notes: Zusätzliche Notizen
        """
        
        timestamp = datetime.now().isoformat()
        
        experiment = {
            "name": experiment_name,
            "timestamp": timestamp,
            "config": config,
            "results": results,
            "notes": notes
        }
        
        # Speichere als JSON
        date_str = timestamp.split('T')[0]
        time_str = timestamp.split('T')[1].split('.')[0].replace(':', '-')
        filename = f"{date_str}_{time_str}_{experiment_name}.json"
        filepath = self.log_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(experiment, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Experiment gespeichert: {filepath}")
        
        # Append to master log
        master_log = self.log_dir / "experiments.jsonl"
        with open(master_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(experiment, ensure_ascii=False) + '\n')
    
    def load_experiments(self) -> list:
        """Lädt alle Experimente"""
        master_log = self.log_dir / "experiments.jsonl"
        
        if not master_log.exists():
            return []
        
        experiments = []
        with open(master_log, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    experiments.append(json.loads(line))
        
        return experiments
    
    def compare_experiments(self, experiment_names: list = None):
        """Vergleicht Experimente"""
        experiments = self.load_experiments()
        
        if not experiments:
            print("⚠️  Noch keine Experimente vorhanden")
            return
        
        if experiment_names:
            experiments = [e for e in experiments if e["name"] in experiment_names]
        
        # Sortiere nach Timestamp
        experiments.sort(key=lambda x: x["timestamp"])
        
        print("=" * 100)
        print("📊 EXPERIMENT VERGLEICH")
        print("=" * 100)
        print(f"{'Name':<30} | {'Top-1':<12} | {'Top-3':<12} | {'Top-5':<12} | {'Datum'}")
        print("-" * 100)
        
        for exp in experiments:
            name = exp["name"]
            date = exp["timestamp"].split('T')[0]
            res = exp["results"]
            
            total = res.get("total", 1)
            
            top1 = res.get("top1_correct", 0)
            top1_pct = f"{top1}/{total} ({top1/total*100:.0f}%)"
            
            top3 = res.get("top3_correct", 0)
            top3_pct = f"{top3}/{total} ({top3/total*100:.0f}%)"
            
            top5 = res.get("top5_correct", 0)
            top5_pct = f"{top5}/{total} ({top5/total*100:.0f}%)"
            
            print(f"{name:<30} | {top1_pct:<12} | {top3_pct:<12} | {top5_pct:<12} | {date}")
        
        print("=" * 100)


# ===== CLI =====

if __name__ == "__main__":
    import sys
    
    tracker = ExperimentTracker()
    
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        # Vergleiche alle Experimente
        tracker.compare_experiments()
    else:
        # Zeige Hilfe
        print("=" * 70)
        print("🧪 EXPERIMENT TRACKER")
        print("=" * 70)
        print()
        print("Verwendung:")
        print("  python experiment_tracker.py compare  # Zeigt alle Experimente")
        print()
        print("Oder importiere in dein Test-Script:")
        print("  from experiment_tracker import ExperimentTracker")
        print("  tracker = ExperimentTracker()")
        print("  tracker.log_experiment(...)")