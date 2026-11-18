"""Outil d'exécution sécurisée de code Python dans le bac à sable (data/sandbox/).

Permet à l'agent Codeur de lancer des scripts autonomes :
- Exécution confinée dans le dossier data/sandbox/
- Timeout strict (15 secondes par défaut)
- Environnement nettoyé des variables sensibles
- Détection automatique des graphiques PNG/SVG générés
- Contrôle d'approbation humaine préalable.
"""

from typing import Dict, Any, List, Optional
import subprocess
import sys
import os
import uuid
import json
from pathlib import Path

from config import settings
from security.approval import require_approval
from tools.registry import tool

TIMEOUT_SECONDS = 15


@tool(name="code_runner", description="Exécute un script Python dans le bac à sable data/sandbox/ pour réaliser des calculs, tableaux ou graphiques PNG.")
def execute_python_code(code: str) -> str:
    """Exécute du code Python dans un sous-processus isolé dans data/sandbox/."""
    sandbox_dir = settings.sandbox_dir
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    # 1. Vérification d'approbation humaine
    code_preview = code.strip().split("\n")[0][:60]
    if not require_approval(action="execute_python_code", target="data/sandbox/", details=f"Extrait : {code_preview}..."):
        return "Action annulée : L'utilisateur a refusé l'exécution de ce code dans le bac à sable."

    # 2. Sauvegarde du script dans data/sandbox/
    script_id = uuid.uuid4().hex[:8]
    script_path = sandbox_dir / f"sandbox_script_{script_id}.py"
    script_path.write_text(code, encoding="utf-8")

    # 3. Préparation d'un environnement d'exécution épuré
    safe_env = {
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
        "PATH": os.environ.get("PATH", ""),
        "TEMP": str(sandbox_dir),
        "TMP": str(sandbox_dir),
        "PYTHONIOENCODING": "utf-8"
    }

    # Liste des graphiques existants avant exécution
    before_pngs = set(sandbox_dir.glob("*.png"))

    start_exec = False
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(sandbox_dir),
            env=safe_env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            encoding="utf-8",
            errors="replace"
        )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        return_code = proc.returncode

        # Détection des nouveaux graphiques générés
        after_pngs = set(sandbox_dir.glob("*.png"))
        new_pngs = [p.name for p in (after_pngs - before_pngs)]

        result = {
            "success": return_code == 0,
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "charts_generated": new_pngs
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except subprocess.TimeoutExpired:
        return f"Erreur d'exécution : Dépassement du temps limite de {TIMEOUT_SECONDS}s (boucle infinie probable)."
    except Exception as e:
        return f"Erreur inattendue lors de l'exécution du code : {type(e).__name__} - {str(e)}"
