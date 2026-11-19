"""Diagnostic de l'environnement (Phase 0).

Vérifie : version de Python, carte graphique, espace disque, Ollama, présence des
3 modèles du .env, un échange avec chaque modèle de discussion et un embedding.
Affiche le temps de chaque test.

    python scripts/check_env.py            # diagnostic complet
    python scripts/check_env.py --quick    # sans appel aux modèles (rapide)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings  # noqa: E402

OK, KO, WARN = "[OK]", "[ÉCHEC]", "[ATTENTION]"
results: list[bool] = []


def report(ok: bool | None, label: str, detail: str = "") -> None:
    status = OK if ok else (WARN if ok is None else KO)
    print(f"{status:<12} {label}{' — ' + detail if detail else ''}")
    if ok is False:
        results.append(False)


def ollama_get(path: str, timeout: float = 5) -> dict:
    with urllib.request.urlopen(f"{settings.ollama_base_url.rstrip('/')}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ollama_post(path: str, payload: dict, timeout: float = 600) -> dict:
    req = urllib.request.Request(
        f"{settings.ollama_base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true", help="ne pas appeler les modèles")
    args = parser.parse_args()

    print("=" * 70)
    print("  DIAGNOSTIC DE L'ENVIRONNEMENT — Système multi-agents local")
    print("=" * 70)

    # 1. Python
    v = sys.version_info
    report(v >= (3, 11), "Python", f"{v.major}.{v.minor}.{v.micro} (3.11 ou plus requis)")

    # 2. Carte graphique
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            report(True, "Carte graphique NVIDIA", out or "détectée")
        except Exception as exc:
            report(None, "Carte graphique NVIDIA", f"nvidia-smi a échoué : {exc}")
    else:
        report(None, "Carte graphique NVIDIA", "non détectée : les modèles tourneront sur le processeur (lent)")

    # 3. Disque
    free_gb = shutil.disk_usage(BASE_DIR).free / 1e9
    report(free_gb > 5, "Espace disque libre", f"{free_gb:.1f} Go")

    # 4. Ollama
    try:
        tags = ollama_get("/api/tags")
    except Exception as exc:
        report(False, "Ollama", f"injoignable à {settings.ollama_base_url} ({exc}). Lance Ollama puis réessaie.")
        return finish()
    installed = [m["name"] for m in tags.get("models", [])]
    report(True, "Ollama", f"répond à {settings.ollama_base_url} ({len(installed)} modèle(s) installé(s))")

    # 5. Modèles du .env
    def present(name: str) -> str | None:
        for m in installed:
            if m == name or (":" not in name and m.split(":")[0] == name):
                return m
        return None

    wanted = {
        "planificateur (MODEL_PLANNER)": settings.model_planner,
        "code (MODEL_CODER)": settings.model_coder,
        "embeddings (MODEL_EMBEDDING)": settings.model_embedding,
    }
    found: dict[str, str | None] = {}
    for label, name in wanted.items():
        found[name] = present(name)
        report(bool(found[name]), f"Modèle {label}", name if found[name] else f"{name} absent → ollama pull {name}")

    if args.quick:
        return finish()

    # 6. Un échange avec chaque modèle de discussion
    for name in {settings.model_planner, settings.model_coder}:
        if not found.get(name):
            continue
        t0 = time.time()
        try:
            resp = ollama_post("/api/chat", {
                "model": name, "stream": False, "think": False,
                "messages": [{"role": "user", "content": "Réponds seulement : OK"}],
                "options": {"temperature": 0, "num_predict": 20},
            })
            text = (resp.get("message", {}).get("content") or "").strip().replace("\n", " ")
            tps = resp.get("eval_count", 0) / max(resp.get("eval_duration", 1) / 1e9, 1e-6)
            report(bool(text), f"Échange avec {name}", f"{time.time() - t0:.1f}s, {tps:.1f} tokens/s, réponse : « {text[:40]} »")
        except Exception as exc:
            report(False, f"Échange avec {name}", str(exc))

    # 7. Embedding
    emb = settings.model_embedding
    if found.get(emb):
        t0 = time.time()
        try:
            resp = ollama_post("/api/embed", {"model": emb, "input": "test de mémoire"}, timeout=120)
            dim = len((resp.get("embeddings") or [[]])[0])
            report(dim > 0, f"Embedding avec {emb}", f"{time.time() - t0:.1f}s, vecteur de {dim} dimensions")
        except Exception as exc:
            report(False, f"Embedding avec {emb}", str(exc))

    return finish()


def finish() -> int:
    print("-" * 70)
    if results:
        print(f"{len(results)} problème(s) à corriger avant d'utiliser le système.")
        return 1
    print("Environnement prêt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
