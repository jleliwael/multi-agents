"""Veille programmée (Phase 9).

Enregistre des sujets de veille avec une fréquence ; chaque exécution produit un nouveau
rapport qui met en évidence ce qui a changé depuis le rapport précédent.

    python scripts/veille.py ajouter "IA locale et Ollama" --jours 7
    python scripts/veille.py liste
    python scripts/veille.py lancer            # exécute les veilles arrivées à échéance
    python scripts/veille.py lancer --toutes   # force toutes les veilles
    python scripts/veille.py supprimer 1

Pour l'automatiser chaque matin sous Windows (Planificateur de tâches), une fois :
    schtasks /Create /TN "Veille multi-agents" /SC DAILY /ST 08:00 ^
      /TR "\"C:\\Users\\user\\Desktop\\multi-agents\\.venv\\Scripts\\python.exe\" \"C:\\Users\\user\\Desktop\\multi-agents\\scripts\\veille.py\" lancer"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings  # noqa: E402

VEILLES_FILE = BASE_DIR / "data" / "veilles.json"


def load() -> List[dict]:
    if VEILLES_FILE.exists():
        return json.loads(VEILLES_FILE.read_text(encoding="utf-8"))
    return []


def save(items: List[dict]) -> None:
    VEILLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    VEILLES_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def is_due(v: dict, now: datetime) -> bool:
    last = v.get("dernier_lancement")
    return not last or now - datetime.fromisoformat(last) >= timedelta(days=v["frequence_jours"])


def run_one(v: dict, orchestrator) -> dict:
    previous = v.get("dernier_rapport")
    files = [previous] if previous and Path(previous).is_file() else []
    objective = f"[Type de tâche : veille] Fais une veille sur : {v['sujet']}. Cite chaque information avec son URL."
    if files:
        objective += (" Compare avec le rapport de veille précédent fourni en fichier et commence par une section "
                      "« Ce qui a changé depuis la dernière veille » (nouveautés, informations disparues ou modifiées).")
    result = orchestrator.run(objective=objective, files=files, on_progress=lambda m: print(f"   {m}"))
    v["dernier_lancement"] = datetime.now().isoformat(timespec="seconds")
    v["dernier_rapport"] = result.get("report_path", previous)
    v.setdefault("historique", []).append({"date": v["dernier_lancement"], "rapport": v["dernier_rapport"],
                                           "statut": result.get("status")})
    return v


def main() -> int:
    parser = argparse.ArgumentParser(description="Veille programmée")
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ajouter", help="ajouter un sujet de veille")
    a.add_argument("sujet")
    a.add_argument("--jours", type=int, default=7, help="fréquence en jours (défaut : 7)")
    sub.add_parser("liste", help="voir les veilles enregistrées")
    r = sub.add_parser("lancer", help="exécuter les veilles arrivées à échéance")
    r.add_argument("--toutes", action="store_true", help="ignorer la fréquence")
    d = sub.add_parser("supprimer", help="supprimer une veille par son numéro")
    d.add_argument("numero", type=int)
    args = parser.parse_args()

    items = load()
    if args.cmd == "ajouter":
        items.append({"sujet": args.sujet, "frequence_jours": max(1, args.jours),
                      "cree_le": datetime.now().isoformat(timespec="seconds")})
        save(items)
        print(f"Veille n°{len(items)} ajoutée : « {args.sujet} » tous les {args.jours} jour(s).")
    elif args.cmd == "liste":
        if not items:
            print("Aucune veille enregistrée.")
        for i, v in enumerate(items, 1):
            print(f"{i}. {v['sujet']} — tous les {v['frequence_jours']} j — dernier lancement : "
                  f"{v.get('dernier_lancement', 'jamais')} — rapport : {v.get('dernier_rapport', '—')}")
    elif args.cmd == "supprimer":
        if not 1 <= args.numero <= len(items):
            print("Numéro inconnu.")
            return 1
        removed = items.pop(args.numero - 1)
        save(items)
        print(f"Veille supprimée : « {removed['sujet']} » (les rapports déjà produits sont conservés).")
    elif args.cmd == "lancer":
        now = datetime.now()
        due = [v for v in items if args.toutes or is_due(v, now)]
        if not due:
            print("Aucune veille à lancer aujourd'hui.")
            return 0
        from orchestrator.orchestrator import Orchestrator
        orchestrator = Orchestrator()
        for v in due:
            print(f"Veille : « {v['sujet']} »")
            try:
                run_one(v, orchestrator)
                print(f"   -> rapport : {v['dernier_rapport']}")
            except Exception as exc:
                print(f"   -> échec : {type(exc).__name__} : {exc}")
            save(items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
