"""Moteur d'exécution des étapes du plan par tri topologique.

Ordonne les étapes en respectant rigoureusement leurs dépendances,
détecte les cycles éventuels et exécute chaque étape avec l'agent spécialiste assigné.
"""

from collections import deque
import time
import json
from typing import List, Dict, Any, Callable, Optional

from orchestrator.plan_models import Plan, Step, StepResult, Fact
from memory.short_term import ShortTermMemory
from logging_.journal import journal


def topological_sort_steps(steps: List[Step]) -> List[Step]:
    """Trie les étapes selon leurs dépendances via l'algorithme de Kahn (tri topologique).

    Lève un ValueError en cas de dépendance invalide ou de cycle.
    """
    step_map: Dict[int, Step] = {s.id: s for s in steps}
    all_ids = set(step_map.keys())

    # Vérification que toutes les dépendances pointent vers des étapes existantes
    for s in steps:
        for dep in s.depends_on:
            if dep not in all_ids:
                raise ValueError(f"Dépendance invalide : L'étape {s.id} dépend de l'étape {dep} qui n'existe pas.")

    # Calcul des degrés entrants (in-degrees) et graphe d'adjacence
    in_degree: Dict[int, int] = {s.id: len(s.depends_on) for s in steps}
    adj: Dict[int, List[int]] = {s.id: [] for s in steps}

    for s in steps:
        for dep in s.depends_on:
            adj[dep].append(s.id)

    # File d'attente des étapes sans dépendance préalable
    queue = deque([s.id for s in steps if in_degree[s.id] == 0])
    ordered_steps: List[Step] = []

    while queue:
        current_id = queue.popleft()
        ordered_steps.append(step_map[current_id])

        for neighbor in adj[current_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Détection de cycle
    if len(ordered_steps) != len(steps):
        raise ValueError("Cycle détecté dans les dépendances du plan d'action !")

    return ordered_steps


class PlanRunner:
    """Exécuteur du plan d'action articulé avec la mémoire court terme et le journal."""

    def __init__(self, agent_factory: Optional[Callable[[str], Any]] = None):
        """agent_factory permet d'injecter une fonction créant l'agent par son nom."""
        self.agent_factory = agent_factory

    def _extract_facts_from_output(self, output_text: str) -> List[Fact]:
        """Tente d'extraire les objets Fact d'une réponse au format JSON."""
        facts: List[Fact] = []
        try:
            # Nettoyage d'éventuelles balises markdown
            cleaned = output_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            data = json.loads(cleaned.strip())
            if isinstance(data, dict) and "facts" in data and isinstance(data["facts"], list):
                for f_data in data["facts"]:
                    try:
                        facts.append(Fact.model_validate(f_data))
                    except Exception:
                        pass
        except Exception:
            pass
        return facts

    def execute_plan(self, plan: Plan, memory: ShortTermMemory) -> Dict[str, Any]:
        """Exécute toutes les étapes ordonnées par tri topologique."""
        ordered_steps = topological_sort_steps(plan.steps)
        execution_trace: List[Dict[str, Any]] = []

        for step in ordered_steps:
            context = memory.get_context_for_step(step.depends_on)
            start_time = time.time()
            error_msg: Optional[str] = None
            output_text = ""
            success = True

            try:
                if self.agent_factory:
                    agent = self.agent_factory(step.agent)
                    output_text = agent.run(step.instruction, context=context)
                else:
                    output_text = f"[Exécution simulée] Étape {step.id} réalisée par {step.agent}."
            except Exception as e:
                success = False
                error_msg = f"{type(e).__name__} : {str(e)}"
                output_text = f"Erreur d'exécution de l'étape {step.id} : {error_msg}"

            duration_ms = (time.time() - start_time) * 1000
            extracted_facts = self._extract_facts_from_output(output_text)

            step_result = StepResult(
                step_id=step.id,
                agent=step.agent,
                success=success,
                output_text=output_text,
                facts=extracted_facts,
                error=error_msg
            )

            # Enregistrement dans la mémoire partagée
            memory.add_step_result(step_result)

            # Écriture dans le journal JSONL
            journal.log_event(
                task_id=plan.task_id,
                agent=step.agent,
                action=f"execute_step_{step.id}",
                duration_ms=duration_ms,
                result={"success": success, "facts_extracted": len(extracted_facts)},
                error=error_msg
            )

            execution_trace.append({
                "step_id": step.id,
                "agent": step.agent,
                "success": success,
                "duration_ms": round(duration_ms, 2)
            })

            # Si une étape échoue et bloque la suite, on consigne l'incident
            if not success:
                break

        return {
            "task_id": plan.task_id,
            "status": "COMPLETED" if all(t["success"] for t in execution_trace) else "FAILED",
            "steps_executed": len(execution_trace),
            "trace": execution_trace,
            "facts_total": len(memory.get_facts())
        }
