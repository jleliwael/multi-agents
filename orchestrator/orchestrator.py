"""Orchestrateur central du système multi-agents local.

Relie le Planificateur, le Moteur d'exécution (Runner), la Mémoire court terme,
la boucle d'assurance qualité avec le Critique, et la persistance SQLite.
"""

from typing import List, Dict, Any, Optional, Callable
import time
import uuid
from datetime import datetime, timezone
import json
from pathlib import Path

from config import settings
from orchestrator.plan_models import Plan, Step, StepResult, Fact
from orchestrator.limits import TaskLimits, LimitExceeded
from agents.planner import PlannerAgent
from orchestrator.runner import PlanRunner, topological_sort_steps
from memory.short_term import ShortTermMemory
from logging_.journal import journal
from agents.critic import CriticAgent, CriticEvaluation
from agents.writer import WriterAgent
from storage.repository import task_repository, TaskRepository
from storage.models import TaskRecord
from agents.base import Agent

# Import des outils pour enregistrement dans le registre
import tools.calculator
import tools.files
import tools.datetime_tool
import tools.documents
import tools.citations


def get_active_model() -> str:
    """Détecte si le modèle configuré est disponible dans Ollama, sinon bascule sur le modèle présent."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            installed = [m["name"].split(":")[0] for m in data.get("models", [])] + [m["name"] for m in data.get("models", [])]
            if settings.model_planner in installed:
                return settings.model_planner
            for candidate in ["qwen3:14b", "qwen2.5:14b", "qwen2.5:7b", "mistral", "mistral:latest"]:
                if candidate in installed:
                    return candidate
            if installed:
                return installed[0]
    except Exception:
        pass
    return settings.model_planner


def default_agent_factory(agent_name: str) -> Agent:
    """Fabrique par défaut créant un agent spécialiste avec ses outils autorisés."""
    name_clean = agent_name.lower().strip()
    target_model = get_active_model()

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
    else:
        return Agent(
            name=name_clean,
            role=f"Agent {agent_name}",
            model=target_model,
            tools=["read_document_pages", "calculator"]
        )


class Orchestrator:
    """Chef d'orchestre global pilotant le cycle complet de vie d'une mission."""

    def __init__(
        self,
        planner: Optional[PlannerAgent] = None,
        critic: Optional[CriticAgent] = None,
        writer: Optional[WriterAgent] = None,
        repository: Optional[TaskRepository] = None,
        agent_factory: Optional[Callable[[str], Any]] = None
    ):
        active_m = get_active_model()
        self.planner = planner or PlannerAgent(model=active_m)
        self.critic = critic or CriticAgent(model=active_m)
        self.writer = writer or WriterAgent(model=active_m)
        self.repository = repository or task_repository
        self.agent_factory = agent_factory or default_agent_factory
        self.runner = PlanRunner(agent_factory=self.agent_factory)

    def run(
        self,
        objective: str,
        task_id: Optional[str] = None,
        files: Optional[List[str]] = None,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """Exécute un objectif complet avec boucle de critique et archivage SQLite."""
        tid = task_id or f"task-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        created_at = datetime.now(timezone.utc).isoformat()

        # Initialisation du contrôleur de limites pour cette tâche
        limits = TaskLimits()

        def notify(msg: str) -> None:
            if on_progress:
                on_progress(msg)

        notify(f"Démarrage de la tâche [{tid}] : « {objective} »")

        # 1. Initialisation de la mémoire court terme
        memory = ShortTermMemory(task_id=tid, objective=objective)

        journal.log_event(
            task_id=tid,
            agent="orchestrator",
            action="start_task",
            duration_ms=0,
            result={"objective": objective, "files": files or []}
        )

        # 2. Planification
        notify("Étape 1 : Élaboration du plan d'action par le Planificateur...")
        plan_start = time.time()
        plan: Plan = self.planner.generate_plan(task_id=tid, objective=objective, files=files)
        plan_duration_ms = (time.time() - plan_start) * 1000

        notify(f"Plan généré : Famille '{plan.task_type}' avec {len(plan.steps)} étapes.")
        journal.log_event(
            task_id=tid,
            agent="planner",
            action="plan_generated",
            duration_ms=plan_duration_ms,
            result={"task_type": plan.task_type, "steps_count": len(plan.steps)}
        )

        # 3. Exécution ordonnée des étapes
        ordered_steps = topological_sort_steps(plan.steps)
        total_steps = len(ordered_steps)
        report_path_str = ""
        final_output_text = ""

        for idx, step in enumerate(ordered_steps, start=1):
            notify(f"Étape {idx}/{total_steps} : Exécution par l'agent '{step.agent.upper()}'...")

            # Vérification des limites avant chaque étape
            limits.steps_done = idx - 1
            try:
                limits.check(action=f"etape_{step.id}_{step.agent}")
            except LimitExceeded as exc:
                notify(f"⚠️ Limite atteinte : {exc.reason} — Génération du rapport partiel...")
                return self._generate_partial_result(
                    tid=tid,
                    objective=objective,
                    plan=plan,
                    memory=memory,
                    reason=exc.reason,
                    start_time=start_time,
                    created_at=created_at
                )

            # Traitement spécifique de l'étape de rédaction avec le Critic et révisions
            if step.agent.lower().strip() == "writer":
                final_output_text, report_file = self._execute_writer_with_critic(
                    step=step,
                    plan=plan,
                    memory=memory,
                    notify=notify
                )
                report_path_str = str(report_file)
            else:
                self._execute_standard_step(step=step, plan=plan, memory=memory, notify=notify)

        # Si aucun agent writer n'a été planifié, on génère quand même le rapport canonique
        if not report_path_str:
            notify("Génération du rapport d'archivage final...")
            final_output_text, report_file = self.writer.write_report(
                task_id=tid,
                objective=objective,
                task_type=plan.task_type or "synthese",
                facts=memory.get_facts()
            )
            report_path_str = str(report_file)

        total_duration_ms = (time.time() - start_time) * 1000

        # 4. Enregistrement dans la base SQLite locale
        notify("Enregistrement de la mission dans la base SQLite data/app.db...")
        task_record = TaskRecord(
            task_id=tid,
            objective=objective,
            family=plan.task_type or "synthese",
            plan_json=plan.model_dump_json(),
            status="COMPLETED",
            duration_ms=round(total_duration_ms, 2),
            sources_count=len(memory.get_facts()),
            report_path=report_path_str,
            created_at=created_at
        )
        self.repository.save_task(task_record)

        journal.log_event(
            task_id=tid,
            agent="orchestrator",
            action="finish_task",
            duration_ms=total_duration_ms,
            result={
                "status": "COMPLETED",
                "facts_count": len(memory.get_facts()),
                "report_path": report_path_str
            }
        )

        notify(f"Mission terminée avec succès en {round(total_duration_ms/1000, 2)}s.")

        return {
            "task_id": tid,
            "objective": objective,
            "status": "COMPLETED",
            "family": plan.task_type,
            "plan": plan.model_dump(),
            "report_path": report_path_str,
            "final_output": final_output_text,
            "facts": [f.model_dump() for f in memory.get_facts()],
            "duration_ms": round(total_duration_ms, 2)
        }

    def _execute_standard_step(
        self,
        step: Step,
        plan: Plan,
        memory: ShortTermMemory,
        notify: Callable[[str], None]
    ) -> None:
        """Exécute une étape normale d'extraction, d'analyse ou de code."""
        context = memory.get_context_for_step(step.depends_on)
        start_time = time.time()
        agent = self.agent_factory(step.agent)
        output_text = agent.run(step.instruction, context=context)
        duration_ms = (time.time() - start_time) * 1000

        extracted_facts = self.runner._extract_facts_from_output(output_text)

        step_result = StepResult(
            step_id=step.id,
            agent=step.agent,
            success=True,
            output_text=output_text,
            facts=extracted_facts
        )
        memory.add_step_result(step_result)

        journal.log_event(
            task_id=plan.task_id,
            agent=step.agent,
            action=f"execute_step_{step.id}",
            duration_ms=duration_ms,
            result={"facts_found": len(extracted_facts)}
        )

    def _execute_writer_with_critic(
        self,
        step: Step,
        plan: Plan,
        memory: ShortTermMemory,
        notify: Callable[[str], None]
    ) -> (str, Path):
        """Gère la rédaction du rapport et la boucle de révision avec le Critique."""
        max_revisions = settings.max_revisions
        feedback: Optional[str] = None
        current_report = ""
        report_file: Optional[Path] = None

        for revision in range(max_revisions + 1):
            if revision > 0:
                notify(f"[Révision {revision}/{max_revisions}] Le Critique a demandé des ajustements...")

            # 1. Rédaction du rapport
            current_report, report_file = self.writer.write_report(
                task_id=plan.task_id,
                objective=plan.objective,
                task_type=plan.task_type or "synthese",
                facts=memory.get_facts(),
                feedback=feedback
            )

            # 2. Évaluation par le Critique
            notify("Évaluation de la qualité et des sources par l'agent Critique...")
            critique: CriticEvaluation = self.critic.evaluate(
                instruction=step.instruction,
                output_text=current_report,
                available_facts=memory.get_facts()
            )

            journal.log_event(
                task_id=plan.task_id,
                agent="critic",
                action=f"critique_pass_{revision}",
                duration_ms=0,
                result={
                    "ok": critique.ok,
                    "score": critique.score,
                    "problemes": critique.problemes
                }
            )

            if critique.ok or revision >= max_revisions:
                if not critique.ok:
                    notify(f"Note qualité : {critique.score}/10 (Limite de révisions atteinte, rapport finalisé).")
                else:
                    notify(f"Approbation du Critique validée avec succès (Score : {critique.score}/10).")
                break

            # Préparation du feedback pour la prochaine révision
            feedback = "Problèmes constatés :\n- " + "\n- ".join(critique.problemes)
            if critique.suggestions:
                feedback += "\nSuggestions d'amélioration :\n- " + "\n- ".join(critique.suggestions)

        step_result = StepResult(
            step_id=step.id,
            agent=step.agent,
            success=True,
            output_text=current_report,
            artifacts=[str(report_file)] if report_file else []
        )
        memory.add_step_result(step_result)

        return current_report, report_file

    def _generate_partial_result(
        self,
        tid: str,
        objective: str,
        plan: Plan,
        memory: ShortTermMemory,
        reason: str,
        start_time: float,
        created_at: str
    ) -> Dict[str, Any]:
        """Génère un rapport partiel horodaté quand une limite d'exécution est atteinte."""
        from datetime import datetime

        total_duration_ms = (time.time() - start_time) * 1000
        partial_header = (
            f"# ⚠️ RAPPORT INCOMPLET — LIMITE ATTEINTE\n\n"
            f"> **Raison :** {reason}\n\n"
            f"Les données collectées jusqu'à cet arrêt sont présentées ci-dessous.\n\n"
        )

        # Rapport partiel basé sur les faits disponibles en mémoire
        facts = memory.get_facts()
        partial_body = ""
        if facts:
            partial_body += "## Faits collectés avant l'arrêt\n\n"
            for i, f in enumerate(facts, 1):
                partial_body += f"- [{i}] {f.claim} *(Source : {f.source_name})*\n"
        else:
            partial_body += "Aucun fait n'avait encore été collecté au moment de l'arrêt.\n"

        partial_report = partial_header + partial_body

        # Sauvegarde du rapport partiel
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = settings.reports_dir
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / f"{date_str}_{tid}_INCOMPLET.md"
        report_file.write_text(partial_report, encoding="utf-8")

        # Enregistrement en base SQLite avec statut INCOMPLET
        task_record = TaskRecord(
            task_id=tid,
            objective=objective,
            family=plan.task_type or "synthese",
            plan_json=plan.model_dump_json(),
            status="INCOMPLET",
            duration_ms=round(total_duration_ms, 2),
            sources_count=len(facts),
            report_path=str(report_file),
            created_at=created_at
        )
        self.repository.save_task(task_record)

        journal.log_event(
            task_id=tid,
            agent="orchestrator",
            action="limit_exceeded_partial_report",
            duration_ms=total_duration_ms,
            error=reason,
            result={"status": "INCOMPLET", "facts_count": len(facts), "report_path": str(report_file)}
        )

        return {
            "task_id": tid,
            "objective": objective,
            "status": "INCOMPLET",
            "family": plan.task_type,
            "plan": plan.model_dump(),
            "report_path": str(report_file),
            "final_output": partial_report,
            "facts": [f.model_dump() for f in facts],
            "duration_ms": round(total_duration_ms, 2),
            "limit_reason": reason,
        }
