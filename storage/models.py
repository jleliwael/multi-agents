"""Modèles de données pour la persistance SQLite."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TaskRecord:
    """Enregistrement d'une tâche dans la base SQLite locale."""
    task_id: str
    objective: str
    family: str
    plan_json: str
    status: str
    duration_ms: float
    sources_count: int
    report_path: str
    created_at: str
