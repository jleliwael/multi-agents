"""Télécharge les modèles du .env via l'API Ollama, avec reprise automatique en cas de coupure.

    python scripts/pull_models.py            # les 3 modèles du .env
    python scripts/pull_models.py qwen3:8b   # un modèle précis

Ollama reprend un téléchargement interrompu là où il s'était arrêté : relancer suffit.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings  # noqa: E402


def pull(model: str, attempts: int = 8) -> bool:
    for attempt in range(1, attempts + 1):
        print(f"[{model}] tentative {attempt}/{attempts}", flush=True)
        last_pct = -10
        try:
            req = urllib.request.Request(
                f"{settings.ollama_base_url.rstrip('/')}/api/pull",
                data=json.dumps({"model": model, "stream": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                for raw in resp:
                    event = json.loads(raw.decode("utf-8"))
                    if "error" in event:
                        raise RuntimeError(event["error"])
                    total, done = event.get("total"), event.get("completed")
                    if total and done:
                        pct = int(100 * done / total)
                        if pct >= last_pct + 10:
                            last_pct = pct
                            print(f"[{model}] {event.get('status', '')[:30]} {pct} % ({done / 1e9:.1f}/{total / 1e9:.1f} Go)", flush=True)
                    if event.get("status") == "success":
                        print(f"[{model}] installé ✓", flush=True)
                        return True
        except Exception as exc:
            print(f"[{model}] coupure : {exc} — nouvel essai dans 15 s", flush=True)
            time.sleep(15)
    print(f"[{model}] ÉCHEC après {attempts} tentatives", flush=True)
    return False


if __name__ == "__main__":
    models = sys.argv[1:] or [settings.model_embedding, settings.model_coder, settings.model_planner]
    ok = all([pull(m) for m in models])
    sys.exit(0 if ok else 1)
