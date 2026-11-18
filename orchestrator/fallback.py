"""Module de plans de secours prédéfinis (Fallback Plans).

Génère un plan d'action déterministe et valide en cas d'échec répété
du modèle LLM à produire un JSON valide.
"""

from orchestrator.plan_models import Plan, Step


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


def get_fallback_plan(task_id: str, objective: str) -> Plan:
    """Génère le plan de secours adapté à la famille de tâche détectée."""
    task_family = detect_task_family(objective)

    if task_family == "veille":
        # Plan de secours Veille : Recherche puis Rédaction
        return Plan(
            task_id=task_id,
            objective=objective,
            task_type="veille",
            steps=[
                Step(
                    id=1,
                    agent="researcher",
                    instruction=f"Effectuer une recherche web ciblée et extraire les faits clés sur : {objective}",
                    depends_on=[]
                ),
                Step(
                    id=2,
                    agent="writer",
                    instruction="Rédiger une note de veille structurée en Markdown selon le template veille.md",
                    depends_on=[1]
                )
            ]
        )

    elif task_family == "comparatif":
        # Plan de secours Comparatif : Recherche, Analyse puis Rédaction
        return Plan(
            task_id=task_id,
            objective=objective,
            task_type="comparatif",
            steps=[
                Step(
                    id=1,
                    agent="researcher",
                    instruction=f"Collecter les caractéristiques et spécifications des solutions pour : {objective}",
                    depends_on=[]
                ),
                Step(
                    id=2,
                    agent="analyst",
                    instruction="Construire une matrice comparative des critères et identifier les forces/faiblesses",
                    depends_on=[1]
                ),
                Step(
                    id=3,
                    agent="writer",
                    instruction="Rédiger le rapport comparatif complet et la recommandation selon le template comparatif.md",
                    depends_on=[2]
                )
            ]
        )

    else:
        # Plan de secours Synthèse : Lecture puis Rédaction
        return Plan(
            task_id=task_id,
            objective=objective,
            task_type="synthese",
            steps=[
                Step(
                    id=1,
                    agent="reader",
                    instruction=f"Lire et extraire les faits essentiels des documents pour l'objectif : {objective}",
                    depends_on=[]
                ),
                Step(
                    id=2,
                    agent="writer",
                    instruction="Rédiger le rapport de synthèse final en Markdown selon le template synthese.md",
                    depends_on=[1]
                )
            ]
        )
