"""Couche d'accès aux données (Repository Pattern) pour SQLite.

Découple la logique d'orchestration de la persistance SQL.
"""

from typing import List, Optional
import sqlite3
from pathlib import Path

from storage.models import TaskRecord
from storage.db import get_db_connection, init_db


class TaskRepository:
    """Gestionnaire de persistance pour les enregistrements de tâches."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        # Initialisation systématique de la table sur la base ciblée
        init_db(self.db_path)

    def save_task(self, record: TaskRecord) -> None:
        """Insère ou met à jour une tâche dans la table tasks."""
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                conn.execute("""
                INSERT OR REPLACE INTO tasks (
                    task_id, objective, family, plan_json, status,
                    duration_ms, sources_count, report_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    record.task_id,
                    record.objective,
                    record.family,
                    record.plan_json,
                    record.status,
                    record.duration_ms,
                    record.sources_count,
                    record.report_path,
                    record.created_at
                ))
        finally:
            conn.close()

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Récupère une tâche par son identifiant unique."""
        conn = get_db_connection(self.db_path)
        try:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?;", (task_id,)).fetchone()
            if not row:
                return None
            return TaskRecord(
                task_id=row["task_id"],
                objective=row["objective"],
                family=row["family"],
                plan_json=row["plan_json"],
                status=row["status"],
                duration_ms=row["duration_ms"],
                sources_count=row["sources_count"],
                report_path=row["report_path"],
                created_at=row["created_at"]
            )
        finally:
            conn.close()

    def list_tasks(self, limit: int = 50) -> List[TaskRecord]:
        """Liste les dernières tâches exécutées."""
        conn = get_db_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?;",
                (limit,)
            ).fetchall()
            return [
                TaskRecord(
                    task_id=r["task_id"],
                    objective=r["objective"],
                    family=r["family"],
                    plan_json=r["plan_json"],
                    status=r["status"],
                    duration_ms=r["duration_ms"],
                    sources_count=r["sources_count"],
                    report_path=r["report_path"],
                    created_at=r["created_at"]
                )
                for r in rows
            ]
        finally:
            conn.close()


# Instance singleton du repository
task_repository = TaskRepository()
