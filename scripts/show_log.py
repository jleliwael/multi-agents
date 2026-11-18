"""Script de visualisation CLI du journal d'audit JSONL.

Usage :
    python scripts/show_log.py                        → 20 derniers événements
    python scripts/show_log.py --task-id task-abc123  → événements d'une tâche
    python scripts/show_log.py --last 50              → 50 derniers événements
    python scripts/show_log.py --agent writer         → filtrer par agent
    python scripts/show_log.py --task-id t1 --agent critic → combinaison de filtres

Affichage couleur :
    - Vert  : événements sans erreur
    - Rouge : événements avec champ error non vide
"""

import sys
import json
import argparse
from pathlib import Path

# Accès à la configuration depuis la racine du projet
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings

LOG_FILE = settings.base_dir / "data" / "logs" / "journal.jsonl"

# Codes ANSI pour la couleur (compatibles Windows avec ANSI activé)
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _colorize(text: str, color: str) -> str:
    """Enveloppe un texte dans des codes couleur ANSI."""
    return f"{color}{text}{_RESET}"


def _format_event(event: dict) -> str:
    """Formate un événement JSONL en ligne lisible colorisée."""
    has_error = bool(event.get("error"))
    color = _RED if has_error else _GREEN

    ts = event.get("timestamp", "")[:19].replace("T", " ")
    task_id = event.get("task_id", "")[:12]
    agent = event.get("agent", "")
    action = event.get("action", "")
    duration = f"{event.get('duration_ms', 0):.0f}ms"
    model = event.get("model", "")
    tokens_in = event.get("tokens_in", 0)
    tokens_out = event.get("tokens_out", 0)
    tool = event.get("tool", "")
    source = event.get("source_consulted", "")
    short_result = event.get("short_result", "")
    error = event.get("error", "")

    # Ligne principale
    line = (
        f"{_colorize(ts, _DIM)} "
        f"{_colorize(f'[{task_id}]', _CYAN)} "
        f"{_colorize(agent, _BOLD):<14} "
        f"{_colorize(action, color):<30} "
        f"{_colorize(duration, _DIM):<8}"
    )

    # Champs optionnels
    extras = []
    if model:
        extras.append(f"model={model}")
    if tokens_in or tokens_out:
        extras.append(f"tokens={tokens_in}↑/{tokens_out}↓")
    if tool:
        extras.append(f"tool={tool}")
    if source:
        extras.append(f"src={source[:40]}")
    if extras:
        line += "  " + _colorize(" | ".join(extras), _YELLOW)

    # Résultat court
    if short_result:
        line += f"\n    {_colorize('→ ' + short_result, _DIM)}"
    # Erreur
    if error:
        line += f"\n    {_colorize('✗ ERREUR : ' + str(error), _RED)}"

    return line


def main() -> None:
    """Point d'entrée principal du visualiseur."""
    # Activation des couleurs ANSI sous Windows
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)
    except Exception:
        pass  # Hors Windows ou droits insuffisants → couleurs ignorées

    parser = argparse.ArgumentParser(
        description="Visualiseur du journal d'audit du système multi-agents."
    )
    parser.add_argument("--task-id", "-t", help="Filtrer par identifiant de tâche.")
    parser.add_argument("--last", "-n", type=int, default=20, help="Afficher les N derniers événements (défaut : 20).")
    parser.add_argument("--agent", "-a", help="Filtrer par nom d'agent.")
    args = parser.parse_args()

    if not LOG_FILE.exists():
        print(f"Journal introuvable : {LOG_FILE}")
        print("Aucune tâche n'a encore été exécutée.")
        return

    # Chargement de toutes les lignes
    events = []
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # Filtrage
    if args.task_id:
        events = [e for e in events if args.task_id in e.get("task_id", "")]
    if args.agent:
        events = [e for e in events if args.agent.lower() in e.get("agent", "").lower()]

    # Limitation aux N derniers
    events = events[-args.last:]

    if not events:
        print("Aucun événement correspondant aux critères fournis.")
        return

    # Affichage
    print(
        _colorize(
            f"\n{'─' * 90}\n"
            f"  Journal d'audit — {len(events)} événement(s)"
            + (f" | tâche : {args.task_id}" if args.task_id else "")
            + (f" | agent : {args.agent}" if args.agent else "")
            + f"\n{'─' * 90}",
            _BOLD
        )
    )

    for event in events:
        print(_format_event(event))

    print(_colorize(f"\n{'─' * 90}", _DIM))
    errors = sum(1 for e in events if e.get("error"))
    if errors:
        print(_colorize(f"  ⚠️  {errors} événement(s) en erreur sur {len(events)} affiché(s).", _RED))


if __name__ == "__main__":
    main()
