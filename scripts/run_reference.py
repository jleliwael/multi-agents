"""Script d'évaluation automatisé sur les tâches de référence hors-web.

Lit docs/taches_reference.json, filtre les tâches purement documentaires (sans web),
les exécute via l'orchestrateur, affiche un tableau récapitulatif console
et enregistre le bilan dans data/eval/reference_<date>.json.
"""

from pathlib import Path
import sys

# Ajout de la racine du projet à sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from typing import List, Dict, Any
from datetime import datetime, timezone
import json
import time

from config import settings
from orchestrator.orchestrator import Orchestrator

DOCS_DIR = settings.base_dir / "docs"
EVAL_DIR = settings.base_dir / "data" / "eval"
TACHES_FILE = DOCS_DIR / "taches_reference.json"


def is_offline_task(task: Dict[str, Any]) -> bool:
    """Détecte si une tâche s'exécute sans accès web."""
    entree = task.get("entree", {})
    t_type = entree.get("type", "").lower()
    instr = entree.get("instruction", "").lower()
    sujet = entree.get("sujet", "").lower()

    if "web" in t_type or "web" in instr or "web" in sujet:
        return False
    return True


def run_benchmark_reference(limit: int | None = None) -> None:
    print("=" * 80)
    print("    ÉVALUATION AUTOMATISÉE DU SYSTÈME MULTI-AGENTS — TÂCHES DE RÉFÉRENCE   ")
    print("=" * 80)

    if not TACHES_FILE.exists():
        print(f"Erreur : Fichier de référence introuvable : {TACHES_FILE}")
        return

    with open(TACHES_FILE, "r", encoding="utf-8") as f:
        all_tasks = json.load(f)

    # Filtrage des tâches hors-web
    offline_tasks = [t for t in all_tasks if is_offline_task(t)]
    if limit:
        offline_tasks = offline_tasks[:limit]
    print(f"Total tâches : {len(all_tasks)} | Tâches documentaires locales retenues : {len(offline_tasks)}")
    print("-" * 80)

    orchestrator = Orchestrator()
    eval_results: List[Dict[str, Any]] = []

    for idx, t in enumerate(offline_tasks, start=1):
        task_id = t["id"]
        titre = t["titre"]
        instruction = t["entree"].get("instruction") or t["entree"].get("question") or titre
        fichiers = t["entree"].get("fichiers", [])

        # Remplacement éventuel par les fixtures existantes pour exécution réelle
        available_files = []
        for f in fichiers:
            candidate = settings.base_dir / "tests" / "fixtures" / "exemple.pdf"
            if candidate.exists():
                available_files.append(str(candidate))

        print(f"\n[{idx}/{len(offline_tasks)}] Exécution de {task_id} : « {titre[:50]}... »")

        start_time = time.time()
        err_msg = None
        status = "COMPLETED"
        sources_count = 0
        report_file = ""

        try:
            res = orchestrator.run(
                objective=instruction,
                task_id=f"eval-{task_id}",
                files=available_files
            )
            sources_count = len(res.get("facts", []))
            report_file = res.get("report_path", "")
            status = res.get("status", "COMPLETED")
        except Exception as e:
            status = "FAILED"
            err_msg = f"{type(e).__name__} : {str(e)}"

        duration_sec = round(time.time() - start_time, 2)

        record = {
            "task_id": task_id,
            "titre": titre,
            "difficulte": t.get("difficulte", "Moyen"),
            "statut": status,
            "duree_secondes": duration_sec,
            "sources_count": sources_count,
            "report_path": report_file,
            "erreur": err_msg
        }
        eval_results.append(record)

    # Affichage du tableau récapitulatif
    print("\n" + "=" * 80)
    print("                           TABLEAU RÉCAPITULATIF                           ")
    print("=" * 80)
    print(f"{'TÂCHE':<10} | {'TITRE':<30} | {'STATUT':<10} | {'DURÉE (s)':<10} | {'SOURCES':<8} | {'ERREUR'}")
    print("-" * 80)

    for r in eval_results:
        err_short = (r["erreur"] or "—")[:20]
        titre_short = (r["titre"][:28] + "..") if len(r["titre"]) > 28 else r["titre"]
        print(f"{r['task_id']:<10} | {titre_short:<30} | {r['statut']:<10} | {r['duree_secondes']:<10} | {r['sources_count']:<8} | {err_short}")

    print("=" * 80)

    # Sauvegarde dans data/eval/reference_<date>.json
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    eval_filename = f"reference_{date_tag}.json"
    eval_filepath = EVAL_DIR / eval_filename

    export_payload = {
        "benchmark_date": datetime.now(timezone.utc).isoformat(),
        "tasks_executed": len(eval_results),
        "results": eval_results
    }

    eval_filepath.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rapport d'évaluation exporté avec succès dans : {eval_filepath}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Évaluation des tâches de référence")
    parser.add_argument("--limit", type=int, default=None, help="Nombre max de tâches à exécuter")
    args = parser.parse_args()
    run_benchmark_reference(limit=args.limit)
