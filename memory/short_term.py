"""Mémoire court terme partagée pour l'exécution d'une tâche multi-agents.

Stocke les résultats intermédiaires de chaque étape, la liste consolidée
des faits certifiés (Fact) avec leurs sources, et fournit le contexte
aux agents suivants.
"""

from typing import List, Dict, Any, Optional
from orchestrator.plan_models import StepResult, Fact


class ShortTermMemory:
    """Espace de travail partagé en RAM pendant la durée de vie d'une tâche."""

    def __init__(self, task_id: str, objective: str):
        self.task_id = task_id
        self.objective = objective
        self._step_results: Dict[int, StepResult] = {}
        self._facts: List[Fact] = []
        self._artifacts: List[str] = []

    def add_step_result(self, result: StepResult) -> None:
        """Enregistre le résultat d'une étape et fusionne les faits découverts."""
        self._step_results[result.step_id] = result
        if result.facts:
            self._facts.extend(result.facts)
        if result.artifacts:
            self._artifacts.extend(result.artifacts)

    def add_fact(self, fact: Fact) -> None:
        """Ajoute directement un fait certifié à la mémoire."""
        self._facts.append(fact)

    def get_step_result(self, step_id: int) -> Optional[StepResult]:
        """Retourne le résultat d'une étape spécifique."""
        return self._step_results.get(step_id)

    def get_all_step_results(self) -> Dict[int, StepResult]:
        """Retourne l'ensemble des résultats d'étapes."""
        return dict(self._step_results)

    def get_facts(self) -> List[Fact]:
        """Retourne tous les faits collectés jusqu'à présent."""
        return list(self._facts)

    def get_artifacts(self) -> List[str]:
        """Retourne la liste des fichiers créés pendant la tâche."""
        return list(self._artifacts)

    def get_context_for_step(self, depends_on: List[int]) -> Dict[str, Any]:
        """Construit le contexte ciblé pour un agent en fonction des étapes dont il dépend."""
        context: Dict[str, Any] = {
            "task_id": self.task_id,
            "objective": self.objective,
            "previous_steps": {},
            "available_facts": [f.model_dump() for f in self._facts],
            "artifacts": self._artifacts
        }

        # Injection des résultats des étapes préalables
        for step_id in depends_on:
            if step_id in self._step_results:
                sr = self._step_results[step_id]
                context["previous_steps"][step_id] = {
                    "agent": sr.agent,
                    "output": sr.output_text,
                    "success": sr.success
                }

        return context

    def get_formatted_facts_summary(self) -> str:
        """Produit un résumé lisible en Markdown de tous les faits mémorisés."""
        if not self._facts:
            return "Aucun fait certifié enregistré pour le moment."

        lines = ["### Faits certifiés en mémoire :"]
        for idx, f in enumerate(self._facts, 1):
            src_info = f"{f.source_name}"
            if f.page_or_section:
                src_info += f" ({f.page_or_section})"
            quote = f" — « {f.exact_quote} »" if f.exact_quote else ""
            lines.append(f"{idx}. {f.assertion} [Source: {src_info}{quote}] (Confiance: {f.confidence.value})")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'état complet de la mémoire court terme."""
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "steps_count": len(self._step_results),
            "facts_count": len(self._facts),
            "step_results": {k: v.model_dump() for k, v in self._step_results.items()},
            "facts": [f.model_dump() for f in self._facts],
            "artifacts": self._artifacts
        }
