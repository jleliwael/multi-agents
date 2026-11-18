"""Générateur de l'arborescence des fichiers squelettes pour la Phase 3."""

from pathlib import Path

BASE = Path("C:/Users/user/Desktop/multi-agents")

FILES_TO_CREATE = {
    # Racine
    "main.py": '"""Point d\'entrée principal pour lancer les services backend (FastAPI) et frontend (Streamlit)."""\n',
    "start.ps1": '# Script PowerShell pour démarrer l\'environnement virtuel, l\'API FastAPI et l\'interface Streamlit\nWrite-Host "Démarrage du système multi-agents local..." -ForegroundColor Cyan\n',
    "docker-compose.yml": '# Configuration optionnelle pour exécuter l\'infrastructure locale (ex: Ollama, ChromaDB distant ou PostgreSQL)\nversion: "3.8"\nservices: {}\n',
    "README.md": '# Système Multi-Agents IA Local\n\nPlateforme d\'orchestration multi-agents autonome et 100% locale, sans framework externe.\n',

    # llm/
    "llm/__init__.py": '"""Module d\'interfaçage avec les grands modèles de langage (LLM)."""\n',
    "llm/ollama_llm.py": '"""Client HTTP asynchrone natif vers l\'API locale Ollama (http://localhost:11434)."""\n',
    "llm/claude_llm.py": '"""Adaptateur optionnel vers l\'API Claude d\'Anthropic pour tests comparatifs ou fallback."""\n',

    # agents/
    "agents/__init__.py": '"""Module regroupant les agents spécialistes et leur système d\'enregistrement."""\n',
    "agents/base.py": '"""Classe de base abstraite (BaseAgent) définissant le cycle de vie, les outils et l\'exécution d\'un agent."""\n',
    "agents/registry.py": '"""Registre central des agents instanciables par leur nom et configuration."""\n',
    "agents/planner.py": '"""Agent Planificateur (qwen3:14b) : décompose l\'objectif utilisateur en un graphe d\'étapes JSON (TaskPlan)."""\n',
    "agents/researcher.py": '"""Agent Chercheur Web : prospection documentaire externe et extraction de faits sourcés (Fact)."""\n',
    "agents/analyst.py": '"""Agent Analyste : croisement des données, détection des contradictions et matrices comparatives."""\n',
    "agents/coder.py": '"""Agent Codeur (qwen2.5-coder:7b) : rédaction et exécution de scripts Python dans le bac à sable local."""\n',
    "agents/writer.py": '"""Agent Rédacteur : génération du rapport final en Markdown à partir des faits certifiés et des templates."""\n',
    "agents/critic.py": '"""Agent Critique : vérification de l\'absence d\'hallucinations, conformité des sources et déclenchement des révisions."""\n',

    # orchestrator/
    "orchestrator/__init__.py": '"""Module d\'orchestration et de pilotage du flux de travail multi-agents."""\n',
    "orchestrator/orchestrator.py": '"""Orchestrateur central coordonnant le flux : plan initial, exécution des étapes, boucle de critique et livrable."""\n',
    "orchestrator/plan_models.py": '"""Modèles de données Pydantic définissant TaskPlan, PlanStep, StepResult et CriticEvaluation."""\n',
    "orchestrator/runner.py": '"""Moteur d\'exécution asynchrone des étapes séquentielles ou parallèles du plan."""\n',
    "orchestrator/fallback.py": '"""Gestion des stratégies de repli en cas d\'erreur d\'un agent ou d\'indisponibilité d\'un modèle."""\n',
    "orchestrator/limits.py": '"""Contrôleur de limites d\'exécution : temps maximum, nombre de révisions et quotas de tokens."""\n',

    # tools/
    "tools/__init__.py": '"""Module de boîte à outils (Tools) utilisables par les agents."""\n',
    "tools/registry.py": '"""Registre des outils permettant l\'enregistrement, la découverte et l\'injection des outils aux agents."""\n',
    "tools/calculator.py": '"""Outil de calcul mathématique et arithmétique déterministe pour éviter les erreurs d\'arrondi des LLM."""\n',
    "tools/files.py": '"""Outil de manipulation sécurisée de fichiers dans les répertoires autorisés de data/."""\n',
    "tools/datetime_tool.py": '"""Outil fournissant l\'horodatage, la date courante et le calcul de deltas temporels."""\n',
    "tools/web_search.py": '"""Outil de recherche web en lecture seule avec limitation de requêtes et filtrage de résultats."""\n',
    "tools/documents.py": '"""Outil d\'extraction textuelle page par page pour PDF (PyMuPDF), DOCX (python-docx) et Excel (openpyxl)."""\n',
    "tools/memory_search.py": '"""Outil de recherche sémantique par similarité vectorielle dans ChromaDB."""\n',
    "tools/code_runner.py": '"""Outil d\'exécution sécurisée de code Python en sous-processus isolé dans data/sandbox/."""\n',
    "tools/connectors/__init__.py": '"""Connecteurs spécifiques pour sources de données externes ou bases locales."""\n',

    # memory/
    "memory/__init__.py": '"""Module de gestion de la mémoire court terme et long terme."""\n',
    "memory/short_term.py": '"""Gestionnaire de mémoire court terme partagée (scratchpad de la tâche en cours)."""\n',
    "memory/long_term.py": '"""Gestionnaire de mémoire vectorielle persistante s\'appuyant sur ChromaDB et nomic-embed-text."""\n',
    "memory/chunking.py": '"""Stratégie de découpage documentaire en morceaux (chunks) avec métadonnées de page et chevauchement."""\n',

    # storage/
    "storage/__init__.py": '"""Module de persistance relationnelle et de stockage des données."""\n',
    "storage/db.py": '"""Connexion et gestion du cycle de vie de la base SQLite locale (data/app.db)."""\n',
    "storage/models.py": '"""Schémas des tables SQLite (tâches, étapes, logs, feedbacks utilisateurs)."""\n',
    "storage/repository.py": '"""Couche d\'accès aux données (Repository Pattern) pour découpler la persistance du reste du code."""\n',

    # security/
    "security/__init__.py": '"""Module de sécurité, de contrôle des accès et de garde-fous."""\n',
    "security/paths.py": '"""Validation stricte des chemins de fichiers pour interdire toute écriture hors de data/workspace/ et data/sandbox/."""\n',
    "security/approval.py": '"""Système de blocage et demande d\'approbation humaine (Human-in-the-Loop) pour actions sensibles."""\n',
    "security/sanitizer.py": '"""Nettoyage des entrées utilisateurs et désinfection des sorties pour éviter les injections de prompts."""\n',

    # logging_/
    "logging_/__init__.py": '"""Module de traçabilité et de journalisation des événements."""\n',
    "logging_/journal.py": '"""Écrivain de journal d\'audit JSONL (une ligne JSON par événement dans data/logs/journal.jsonl)."""\n',

    # api/
    "api/__init__.py": '"""Module Backend FastAPI."""\n',
    "api/app.py": '"""Application FastAPI principale configurant les middlewares CORS, le cycle de vie et les routeurs."""\n',
    "api/routes_tasks.py": '"""Routes REST pour soumettre une tâche, consulter son statut et streamer les étapes en direct."""\n',
    "api/routes_feedback.py": '"""Routes REST pour enregistrer les approbations humaines et les notations des livrables."""\n',
    "api/schemas.py": '"""Schémas Pydantic des requêtes et réponses HTTP de l\'API."""\n',

    # ui/
    "ui/app.py": '"""Interface utilisateur Streamlit avec formulaire d\'objectif, suivi en direct et validation humaine."""\n',

    # scripts/
    "scripts/check_env.py": '"""Script de diagnostic vérifiant la présence de Python, GPU, VRAM, Ollama et des modèles requis."""\n',
    "scripts/index_docs.py": '"""Script utilitaire pour ingérer et indexer des dossiers de documents dans ChromaDB."""\n',
    "scripts/run_reference.py": '"""Script pour exécuter l\'une des 10 tâches de référence et mesurer sa performance."""\n',
    "scripts/evaluate.py": '"""Script d\'évaluation automatique de la qualité des livrables par rapport aux critères de référence."""\n',
    "scripts/show_log.py": '"""Visualiseur en ligne de commande pour parser et afficher le journal JSONL avec couleurs."""\n',
    "scripts/feedback_report.py": '"""Générateur de rapport statistique sur les retours utilisateurs et scores de satisfaction."""\n',

    # tests/
    "tests/__init__.py": '"""Package des tests unitaires et d\'intégration."""\n',
    "tests/conftest.py": '"""Fixtures pytest avec simulateur de LLM factice (Mock LLM) pour tests hors-ligne ultra-rapides."""\n',
    "tests/eval/jeu_30_taches.json": '[\n  {\n    "id": "eval-01",\n    "titre": "Tâche d\'évaluation test",\n    "type": "synthese"\n  }\n]\n',

    # docs/
    "docs/rapport_qualite.md": '# Rapport Qualité et Métriques d\'Évaluation\n\nCe document consolide les résultats de référence et les métriques de qualité.\n',
    "docs/guide_utilisation.md": '# Guide d\'Utilisation du Système Multi-Agents\n\nCe guide pas à pas détaille le démarrage, l\'utilisation de l\'API et de l\'interface Streamlit.\n'
}

for rel_path, content in FILES_TO_CREATE.items():
    p = BASE / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(content, encoding="utf-8")
        print(f"Créé : {rel_path}")
    else:
        print(f"Déjà existant : {rel_path}")

print("Initialisation des fichiers de l'arborescence terminée avec succès.")
