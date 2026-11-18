"""Module de journalisation d'audit en format JSONL (une ligne JSON par événement).

Écrit les événements d'exécution dans data/logs/journal.jsonl.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
from datetime import datetime, timezone

from config import settings

LOG_DIR = settings.base_dir / "data" / "logs"
LOG_FILE = LOG_DIR / "journal.jsonl"


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
        tokens: Optional[Dict[str, int]] = None,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enregistre un événement unitaire sous forme d'une ligne JSON."""
        tokens_data = tokens or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # Sérialisation propre du résultat
        res_data = result
        if hasattr(result, "model_dump"):
            res_data = result.model_dump()

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "agent": agent,
            "action": action,
            "duration_ms": round(duration_ms, 2),
            "tokens": tokens_data,
            "result": res_data,
            "error": error
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return event


# Instance unique globale du journal
journal = AuditJournal()
