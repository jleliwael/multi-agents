"""Choix du modèle Ollama réellement disponible.

Le .env indique les modèles souhaités (qwen3:14b, qwen2.5-coder:7b...). Si l'un
d'eux n'est pas installé, on bascule sur le meilleur modèle présent pour que le
système reste utilisable. La liste des modèles installés est mise en cache
quelques secondes pour éviter d'interroger Ollama à chaque création d'agent.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import List, Optional

from config import settings

# Ordre de préférence quand le modèle demandé est absent
FALLBACK_ORDER: List[str] = [
    "qwen3:14b", "qwen3:8b", "qwen2.5:14b", "qwen2.5:7b", "llama3.1:8b", "mistral:latest", "mistral",
]
_CACHE_SECONDS = 30.0
_cache: dict = {"at": 0.0, "models": []}


def installed_models(force: bool = False) -> List[str]:
    """Retourne les noms des modèles installés dans Ollama (liste vide si Ollama est éteint)."""
    now = time.time()
    if not force and now - _cache["at"] < _CACHE_SECONDS:
        return list(_cache["models"])
    models: List[str] = []
    try:
        req = urllib.request.Request(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        models = []
    _cache.update(at=now, models=models)
    return list(models)


def _is_installed(name: str, models: List[str]) -> Optional[str]:
    """Retourne le nom exact installé correspondant à `name` (avec ou sans tag)."""
    for m in models:
        if m == name or m.split(":")[0] == name or (":" not in name and m == f"{name}:latest"):
            return m
    return None


def resolve_model(preferred: Optional[str] = None) -> str:
    """Retourne `preferred` s'il est installé, sinon le meilleur modèle disponible.

    Si Ollama ne répond pas, renvoie le modèle demandé tel quel : l'erreur claire
    sera levée au premier appel par OllamaLLM.
    """
    wanted = preferred or settings.model_planner
    models = installed_models()
    if not models:
        return wanted
    exact = _is_installed(wanted, models)
    if exact:
        return exact
    for candidate in FALLBACK_ORDER:
        exact = _is_installed(candidate, models)
        if exact:
            return exact
    # On évite de choisir un modèle d'embedding pour discuter
    chat_models = [m for m in models if "embed" not in m]
    return chat_models[0] if chat_models else wanted
