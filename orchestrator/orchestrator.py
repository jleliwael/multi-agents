"""Orchestrateur central du système multi-agents local.

Relie le Planificateur, le Moteur d'exécution (Runner), la Mémoire court terme
et le Journal d'audit pour mener à bien un objectif de bout en bout.
"""

from typing import List, Dict, Any, Optional, Callable
import time
import uuid

from config import settings
from orchestrator.plan_models import Plan
from agents.planner import PlannerAgent
from orchestrator.runner import PlanRunner
from memory.short_term import ShortTermMemory
from logging_.journal import journal
from agents.base import Agent

# Import des outils pour enregistrement dans le registre
import tools.calculator
import tools.files
import tools.datetime_tool
import tools.documents


def default_agent_factory(agent_name: str) -> Agent:
    """Fabrique par défaut créant un agent spécialiste avec ses outils autorisés."""
    name_clean = agent_name.lower().strip()

    if name_clean == "reader":
        return Agent(
            name="reader",
            role="Lecteur de Documents et Mémoire",
            model=settings.model_planner,
            tools=["read_document_pages", "read_file", "list_files"]
        )
    elif name_clean == "researcher":
        return Agent(
            name="researcher",
            role="Chercheur Web Documentaire",
            model=settings.model_planner,
            tools=["get_current_datetime"]
        )
    elif name_clean == "analyst":
        return Agent(
            name="analyst",
            role="Analyste et Comparateur",
            model=settings.model_planner,
            tools=["calculator"]
        )
    elif name_clean == "coder":
        return Agent(
            name="coder",
            role="Codeur Python Sandbox",
            model=settings.model_coder,
            tools=["calculator"]
        )
    elif name_clean == "writer":
        return Agent(
            name="writer",
            role="Rédacteur de Rapports Markdown",
            model=settings.model_planner,
            tools=["write_file"]
        )
    elif name_clean == "critic":
        return Agent(
            name="critic",
            role="Critique et Assurance Qualité",
            model=settings.model_planner,
            tools=[]
        )
    else:
        return Agent(
            name=name_clean,
            role=f"Agent {agent_name}",
            model=settings.model_planner,
            tools=["read_document_pages", "calculator"]
        )


class Orchestrator:
    """Chef d'orchestre global coordonnant la planification et l'exécution."""

    def __init__(
        self,
        planner: Optional[PlannerAgent] = None,
        agent_factory: Optional[Callable[[str], Any]] = None
    ):
        self.planner = planner or PlannerAgent()
        self.agent_factory = agent_factory or default_agent_factory
        self.runner = PlanRunner(agent_factory=self.agent_factory)

    def run(
        self,
        objective: str,
        task_id: Optional[str] = None,
        files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Exécute un objectif complet de bout en bout."""
        tid = task_id or f"task-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        # 1. Initialisation de la mémoire court terme
        memory = ShortTermMemory(task_id=tid, objective=objective)

        journal.log_event(
            task_id=tid,
            agent="orchestrator",
            action="start_task",
            duration_ms=0,
            result={"objective": objective, "files": files or []}
        )

        # 2. Élaboration du plan d'action
        plan_start = time.time()
        plan: Plan = self.planner.generate_plan(task_id=tid, objective=objective, files=files)
        plan_duration_ms = (time.time() - plan_start) * 1000

        journal.log_event(
            task_id=tid,
            agent="planner",
            action="plan_generated",
            duration_ms=plan_duration_ms,
            result={"task_type": plan.task_type, "steps_count": len(plan.steps)}
        )

        # 3. Exécution du plan via le Runner
        execution_report = self.runner.execute_plan(plan, memory)

        total_duration_ms = (time.time() - start_time) * 1000

        # Récupération du résultat final (dernière étape exécutée)
        last_step_result = None
        if plan.steps:
            last_step_id = plan.steps[-1].id
            last_step_result = memory.get_step_result(last_step_id)

        final_output = last_step_result.output_text if last_step_result else "Aucun livrable généré."

        journal.log_event(
            task_id=tid,
            agent="orchestrator",
            action="finish_task",
            duration_ms=total_duration_ms,
            result={
                "status": execution_report["status"],
                "facts_count": len(memory.get_facts()),
                "steps_executed": execution_report["steps_executed"]
            }
        )

        return {
            "task_id": tid,
            "objective": objective,
            "status": execution_report["status"],
            "plan": plan.model_dump(),
            "execution": execution_report,
            "final_output": final_output,
            "facts": [f.model_dump() for f in memory.get_facts()],
            "duration_ms": round(total_duration_ms, 2)
        }
