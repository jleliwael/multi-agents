"""Module de journalisation d'audit en format JSONL (une ligne JSON par événement).

Écrit les événements d'exécution dans data/logs/journal.jsonl.

Champs enrichis (Phase 6) :
- model : nom du modèle LLM utilisé
- tokens_in / tokens_out : tokens consommés par l'appel
- tool : nom de l'outil appelé (si applicable)
- source_consulted : URL ou nom de fichier consulté
- short_result : aperçu tronqué à 100 caractères du résultat
- Masquage automatique des clés API avant écriture
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import re
from datetime import datetime, timezone

from config import settings

LOG_DIR = settings.base_dir / "data" / "logs"
LOG_FILE = LOG_DIR / "journal.jsonl"

# Patterns de masquage des secrets (nom de clé → remplacé par ***)
_SECRET_KEY_PATTERNS: list[re.Pattern] = [
    re.compile(r"(api[_-]?key|secret|password|token|bearer|authorization)", re.IGNORECASE),
]


def _mask_secrets(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remplace récursivement les valeurs sensibles par '***'.

    Détecte les clés dont le nom contient 'api_key', 'secret', 'password', etc.
    Ne modifie pas l'objet original (copie superficielle).
    """
    if not isinstance(data, dict):
        return data
    masked = {}
    for k, v in data.items():
        # Si la clé ressemble à un secret ET que la valeur est une chaîne non vide → masquer
        is_secret_key = any(pat.search(str(k)) for pat in _SECRET_KEY_PATTERNS)
        if is_secret_key and isinstance(v, str) and v.strip():
            masked[k] = "***"
        elif isinstance(v, dict):
            masked[k] = _mask_secrets(v)
        elif isinstance(v, list):
            masked[k] = [_mask_secrets(i) if isinstance(i, dict) else i for i in v]
        else:
            masked[k] = v
    return masked


def _short_result(result: Any, max_chars: int = 100) -> str:
    """Génère un aperçu tronqué d'un résultat pour le journal."""
    if result is None:
        return ""
    text = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
    text = text.replace("\n", " ").strip()
    return text[:max_chars] + "…" if len(text) > max_chars else text


class AuditJournal:
    """Gestionnaire d'écriture thread-safe pour le journal JSONL."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_file = log_path or LOG_FILE
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        task_id: str,
        agent: str,
        action: str,
        duration_ms: float,
        # Champs enrichis Phase 6
        model: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        tool: str = "",
        source_consulted: str = "",
        # Champs existants
        tokens: Optional[Dict[str, int]] = None,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enregistre un événement unitaire sous forme d'une ligne JSON.

        Les valeurs de clés API présentes dans `result` sont automatiquement masquées.
        """
        tokens_data = tokens or {"prompt_tokens": tokens_in, "completion_tokens": tokens_out, "total_tokens": tokens_in + tokens_out}

        # Sérialisation propre du résultat
        res_data = result
        if hasattr(result, "model_dump"):
            res_data = result.model_dump()

        event: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "agent": agent,
            "action": action,
            "duration_ms": round(duration_ms, 2),
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tool": tool,
            "source_consulted": source_consulted,
            "short_result": _short_result(res_data),
            "tokens": tokens_data,
            "result": res_data,
            "error": error,
        }

        # Masquage des secrets avant écriture
        safe_event = _mask_secrets(event)

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(safe_event, ensure_ascii=False) + "\n")

        return event  # Retourne l'événement non masqué pour usage interne


# Instance unique globale du journal
journal = AuditJournal()
