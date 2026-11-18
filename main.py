"""Point d'entrée principal en ligne de commande (CLI).

Permet d'exécuter soit le pipeline multi-agents complet, soit un agent spécifique :
Exemple Pipeline Complet :
    python main.py "Analyser ces documents et produire une synthèse" --files tests/fixtures/exemple.pdf
Exemple Démonstration Mono-Agent :
    python main.py --agent reader "Extraire les points clés de exemple.pdf"
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import json
import urllib.request

from config import settings
from orchestrator.orchestrator import Orchestrator
from agents.planner import PlannerAgent
from agents.base import Agent
import tools.documents


def get_available_ollama_models() -> List[str]:
    """Interroge l'API Ollama locale pour obtenir la liste des modèles installés."""
    try:
        req = urllib.request.Request(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                models.append(name)
                if ":" in name:
                    models.append(name.split(":")[0])
            return models
    except Exception:
        return []


def resolve_best_model(model_override: Optional[str] = None) -> str:
    """Détermine le meilleur modèle disponible dans Ollama."""
    available = get_available_ollama_models()
    if model_override and (model_override in available or not available):
        return model_override

    # Priorité aux modèles configurés dans le .env
    for target in [settings.model_planner, "qwen3:14b", "qwen2.5:14b", "qwen2.5:7b", "mistral", "mistral:latest"]:
        if target in available:
            return target

    return available[0] if available else settings.model_planner


def build_custom_agent_factory(target_model: str):
    """Génère une fabrique d'agents configurée avec le modèle sélectionné."""
    def factory(agent_name: str) -> Agent:
        name_clean = agent_name.lower().strip()
        if name_clean == "reader":
            return Agent(
                name="reader",
                role="Lecteur de Documents et Mémoire",
                model=target_model,
                tools=["read_document_pages", "read_file", "list_files"]
            )
        elif name_clean == "researcher":
            return Agent(
                name="researcher",
                role="Chercheur Web Documentaire",
                model=target_model,
                tools=["get_current_datetime"]
            )
        elif name_clean == "analyst":
            return Agent(
                name="analyst",
                role="Analyste et Comparateur",
                model=target_model,
                tools=["calculator"]
            )
        elif name_clean == "coder":
            return Agent(
                name="coder",
                role="Codeur Python Sandbox",
                model=target_model,
                tools=["calculator"]
            )
        elif name_clean == "writer":
            return Agent(
                name="writer",
                role="Rédacteur de Rapports Markdown",
                model=target_model,
                tools=["write_file"]
            )
        elif name_clean == "critic":
            return Agent(
                name="critic",
                role="Critique et Assurance Qualité",
                model=target_model,
                tools=[]
            )
        return Agent(
            name=name_clean,
            role=f"Agent {agent_name}",
            model=target_model,
            tools=["read_document_pages", "calculator"]
        )
    return factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Système Multi-Agents Local — Plateforme d'Exécution")
    parser.add_argument(
        "objective",
        type=str,
        nargs="?",
        default="Résumer les points stratégiques de exemple.pdf avec les sources",
        help="Objectif global de la mission en langage naturel"
    )
    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Nom d'un agent spécifique pour un test unitaire (ex: reader, analyst, coder)"
    )
    parser.add_argument(
        "--files",
        type=str,
        nargs="*",
        default=[],
        help="Fichiers d'entrée à traiter (ex: doc1.pdf doc2.docx)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Modèle Ollama à utiliser (par défaut détection automatique)"
    )
    args = parser.parse_args()

    active_model = resolve_best_model(args.model)
    agent_factory = build_custom_agent_factory(active_model)

    print("=" * 70)
    print("           SYSTÈME MULTI-AGENTS IA LOCAL (WINDOWS 11 / OLLAMA)           ")
    print("=" * 70)
    print(f"URL Ollama Locale : {settings.ollama_base_url}")
    print(f"Modèle Actif      : {active_model}")
    print(f"Objectif reçu     : « {args.objective} »")
    if args.files:
        print(f"Fichiers cibles   : {args.files}")
    print("-" * 70)

    # 1. Mode mono-agent spécifique
    if args.agent:
        print(f"Mode Mono-Agent sélectionné : '{args.agent.upper()}'")
        agent = agent_factory(args.agent)
        try:
            print("[1/2] Lancement de l'agent...")
            result = agent.run(task=args.objective)
            print("[2/2] Résultat produit :")
            print("-" * 70)
            print(result)
            print("-" * 70)
        except ConnectionError as ce:
            print(f"\n[INFO HORS-LIGNE] {ce}")
            print("Démonstration autonome de l'outil documents :")
            print(tools.documents.read_document_pages("tests/fixtures/exemple.pdf", max_pages=2))
        return

    # 2. Mode Pipeline Multi-Agents complet
    print("Mode Pipeline Multi-Agents Orchestré activé...")
    planner = PlannerAgent(model=active_model)
    orchestrator = Orchestrator(planner=planner, agent_factory=agent_factory)

    def print_progress(msg: str) -> None:
        print(f"--> {msg}")

    try:
        execution_result = orchestrator.run(
            objective=args.objective,
            files=args.files,
            on_progress=print_progress
        )

        print("\n" + "=" * 70)
        print("                         LIVRABLE FINAL GÉNÉRÉ                       ")
        print("=" * 70)
        print(f"Statut Mission  : {execution_result['status']}")
        print(f"Famille Tâche   : {execution_result['family']}")
        print(f"Durée Totale    : {execution_result['duration_ms']} ms")
        print(f"Faits Certifiés : {len(execution_result['facts'])}")
        print(f"Chemin Rapport  : {execution_result['report_path']}")
        print("-" * 70)
        print(execution_result['final_output'])
        print("=" * 70)

    except ConnectionError as ce:
        print(f"\n[INFO HORS-LIGNE] {ce}")
        print("Pour lancer le pipeline complet avec inférence, démarre Ollama : 'ollama serve'.")


if __name__ == "__main__":
    main()
