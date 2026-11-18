"""Point d'entrée principal et démonstration en ligne de commande (CLI).

Permet d'exécuter un agent spécifique en mode démonstration :
Usage : python main.py --agent reader "Résume le document tests/fixtures/exemple.pdf en 5 points avec les pages"
"""

import argparse
import json
import urllib.request
from typing import List

# Chargement de la configuration
from config import settings

# Enregistrement des outils
import tools.calculator
import tools.files
import tools.datetime_tool
import tools.documents
from tools.registry import registry

from agents.base import Agent
from llm.ollama_llm import OllamaLLM


def get_available_ollama_models() -> List[str]:
    """Interroge l'API Ollama locale pour obtenir la liste des modèles installés."""
    try:
        req = urllib.request.Request(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m["name"].split(":")[0] for m in data.get("models", [])] + [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def build_agent(agent_name: str, model_override: str | None = None) -> Agent:
    """Instancie un agent avec ses outils dédiés et sélection intelligente du modèle disponible."""
    name_clean = agent_name.lower().strip()
    available_models = get_available_ollama_models()

    # Choix du modèle : argument CLI prioritaire, sinon .env, sinon premier modèle disponible
    target_model = model_override or settings.model_planner
    if target_model not in available_models and available_models:
        # Fallback automatique sur un modèle installé si le modèle cible n'est pas encore téléchargé
        for candidate in ["qwen3:14b", "qwen2.5:14b", "qwen2.5:7b", "mistral", "mistral:latest"]:
            if candidate in available_models:
                target_model = candidate
                break
        else:
            target_model = available_models[0]

    if name_clean == "reader":
        return Agent(
            name="reader",
            role="Lecteur de Documents et Mémoire",
            model=target_model,
            tools=["read_document_pages", "read_file", "list_files"]
        )
    elif name_clean == "analyst":
        return Agent(
            name="analyst",
            role="Analyste documentaire",
            model=target_model,
            tools=["calculator"]
        )
    else:
        return Agent(
            name=name_clean,
            role=f"Agent {agent_name}",
            model=target_model,
            tools=["read_document_pages", "calculator", "get_current_datetime"]
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Système Multi-Agents Local — Démonstration CLI")
    parser.add_argument(
        "--agent",
        type=str,
        default="reader",
        help="Nom de l'agent à exécuter (ex: reader, analyst, planner)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Modèle Ollama à utiliser (optionnel : détecte automatiquement les modèles installés)"
    )
    parser.add_argument(
        "task",
        type=str,
        nargs="?",
        default="Résume le document tests/fixtures/exemple.pdf en 5 points avec les pages",
        help="Objectif ou question à transmettre à l'agent"
    )
    args = parser.parse_args()

    agent = build_agent(args.agent, model_override=args.model)

    print("=" * 65)
    print(f"   SYSTÈME MULTI-AGENTS LOCAL — EXÉCUTION DE L'AGENT '{args.agent.upper()}'")
    print("=" * 65)
    print(f"Modèle actif     : {agent.model}")
    print(f"URL Ollama       : {settings.ollama_base_url}")
    print(f"Tâche reçue      : {args.task}")
    print("-" * 65)

    try:
        print("[1/2] Lancement de l'agent et consultation des outils...")
        result = agent.run(task=args.task)
        print("[2/2] Réponse produite par l'agent :")
        print("-" * 65)
        print(result)
        print("-" * 65)
        print("Démonstration terminée avec succès.")

    except ConnectionError as ce:
        print("\n[INFO OLLAMA HORS-LIGNE]")
        print(f"{ce}")
        print("\n--> Démonstration du fonctionnement autonome de l'outil 'documents' :")
        doc_output = tools.documents.read_document_pages("tests/fixtures/exemple.pdf", max_pages=3)
        print(doc_output)


if __name__ == "__main__":
    main()
