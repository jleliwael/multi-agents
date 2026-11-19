"""Module de plans de secours prédéfinis (Fallback Plans).

Génère un plan d'action déterministe et valide en cas d'échec répété
du modèle LLM à produire un JSON valide.
"""

import re
from typing import List, Optional

from orchestrator.plan_models import Plan, Step


FAMILY_PREFIX = re.compile(r"^\s*\[Type de tâche\s*:\s*(\w+)\]\s*", re.I)
KNOWN_FAMILIES = {"synthese", "veille", "comparatif", "question"}


def forced_family(objective: str) -> Optional[str]:
    """Famille imposée par l'interface (« [Type de tâche : question] ... »), sinon None."""
    match = FAMILY_PREFIX.match(objective or "")
    if match and match.group(1).lower() in KNOWN_FAMILIES:
        return match.group(1).lower()
    return None


def detect_task_family(objective: str) -> str:
    """Détecte la famille de tâche à partir des mots-clés de l'objectif."""
    obj_clean = objective.lower()

    # Mots-clés de comparatif / benchmark
    if any(k in obj_clean for k in ["comparer", "comparatif", "benchmark", " vs ", "différence", "grille"]):
        return "comparatif"

    # Mots-clés de veille web
    if any(k in obj_clean for k in ["veille", "actualité", "web", "tendance", "récent", "marché"]):
        return "veille"

    # Par défaut : synthèse documentaire
    return "synthese"


def get_fallback_plan(task_id: str, objective: str, files: Optional[List[str]] = None,
                      family: Optional[str] = None) -> Plan:
    """Génère le plan de secours adapté à la famille de tâche détectée.

    Si des fichiers sont fournis, le plan commence toujours par leur lecture
    (le Lecteur reçoit la liste exacte des fichiers) ; la recherche web n'est
    ajoutée que pour une veille.
    """
    task_family = family or detect_task_family(objective)
    files = list(files or [])
    files_txt = ", ".join(files)
    read_instruction = (
        f"Lire les fichiers fournis ({files_txt}) avec l'outil read_document_pages et extraire, "
        f"avec leur source et leur page, les faits utiles pour : {objective}"
    )
    steps: List[Step] = []

    if task_family == "veille":
        steps.append(Step(id=1, agent="researcher",
                          instruction=f"Effectuer une recherche web ciblée et extraire les faits clés sur : {objective}"))
        if files:
            steps.append(Step(id=2, agent="reader", instruction=read_instruction))
        steps.append(Step(id=len(steps) + 1, agent="writer",
                          instruction="Rédiger une note de veille structurée en Markdown selon le template veille.md",
                          depends_on=[s.id for s in steps]))
    elif task_family == "comparatif":
        if files:
            steps.append(Step(id=1, agent="reader", instruction=read_instruction))
        else:
            steps.append(Step(id=1, agent="researcher",
                              instruction=f"Collecter les caractéristiques et spécifications des solutions pour : {objective}"))
        steps.append(Step(id=2, agent="analyst",
                          instruction="Construire une matrice comparative des critères et identifier les forces/faiblesses",
                          depends_on=[1]))
        steps.append(Step(id=3, agent="writer",
                          instruction="Rédiger le rapport comparatif complet et la recommandation selon le template comparatif.md",
                          depends_on=[2]))
    else:
        steps.append(Step(id=1, agent="reader", instruction=read_instruction if files else
                          f"Lire et extraire les faits essentiels des documents pour l'objectif : {objective}"))
        template = "question.md (réponse directe et courte)" if task_family == "question" else "synthese.md"
        steps.append(Step(id=2, agent="writer",
                          instruction=f"Rédiger le rapport final en Markdown selon le template {template}",
                          depends_on=[1]))

    return Plan(task_id=task_id, objective=objective, task_type=task_family, steps=steps)
