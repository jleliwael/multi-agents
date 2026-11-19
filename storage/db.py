"""Initialisation et gestion de la base de données SQLite locale (data/app.db)."""

import sqlite3
from pathlib import Path
from typing import Optional
from config import settings


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Ouvre une connexion SQLite avec le mode Write-Ahead Logging (WAL) activé."""
    path = db_path or settings.sqlite_db_path
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    # Activation du mode WAL pour concurrence et robustesse
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Crée les tables SQLite si elles n'existent pas encore."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                objective TEXT NOT NULL,
                family TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                sources_count INTEGER NOT NULL,
                report_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            # Phase 9 : avis des utilisateurs (👍 = 1, 👎 = -1) sur un rapport ou une section
            conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                rating INTEGER NOT NULL,
                section TEXT NOT NULL DEFAULT 'rapport',
                comment TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            """)
    finally:
        conn.close()


# Initialisation automatique au chargement
init_db()
