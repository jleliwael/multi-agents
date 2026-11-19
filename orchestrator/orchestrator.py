"""Orchestrateur central du système multi-agents local.

Relie le Planificateur, le Moteur d'exécution (Runner), la Mémoire court terme,
la boucle d'assurance qualité avec le Critique, et la persistance SQLite.
"""

from typing import List, Dict, Any, Optional, Callable
import contextvars
import threading
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
from agents.registry import make_agent_factory
from orchestrator.fallback import forced_family, get_fallback_plan
from llm.model_resolver import resolve_model
from concurrent.futures import ThreadPoolExecutor


def get_active_model() -> str:
    """Modèle du planificateur réellement disponible (bascule si qwen3:14b est absent)."""
    return resolve_model(settings.model_planner)


def default_agent_factory(agent_name: str) -> Agent:
    """Fabrique par défaut : outils et modèle définis dans agents/registry.py."""
    return make_agent_factory()(agent_name)


def group_steps_in_waves(steps: List[Step]) -> List[List[Step]]:
    """Regroupe les étapes par « vague » : une vague ne contient que des étapes
    dont toutes les dépendances sont dans les vagues précédentes.
    Les étapes d'une même vague sont indépendantes et peuvent tourner en parallèle.
    L'ordre topologique est conservé (tri préalable)."""
    ordered = topological_sort_steps(steps)
    level: Dict[int, int] = {}
    for step in ordered:
        deps = [level[d] for d in step.depends_on if d in level]
        level[step.id] = (max(deps) + 1) if deps else 0
    waves: Dict[int, List[Step]] = {}
    for step in ordered:
        waves.setdefault(level[step.id], []).append(step)
    return [waves[k] for k in sorted(waves)]


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
        # Planificateur et Critique : Claude si ANTHROPIC_API_KEY est renseignée, sinon Ollama
        from llm.claude_llm import make_reasoning_llm
        self.planner = planner or PlannerAgent(model=active_m, llm_client=make_reasoning_llm())
        self.critic = critic or CriticAgent(model=active_m, llm_client=make_reasoning_llm())
        self.writer = writer or WriterAgent(model=active_m)
        self.repository = repository or task_repository
        self.agent_factory = agent_factory or default_agent_factory
        self.runner = PlanRunner(agent_factory=self.agent_factory)
        self._memory_lock = threading.Lock()

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
        memory.files = list(files or [])  # transmis à chaque agent dans son contexte

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
        family = forced_family(objective)
        if family == "question" and files:
            # Question sur des documents : plan direct Lecteur -> Rédacteur (rapide et fiable)
            plan = get_fallback_plan(tid, objective, files, family="question")
        else:
            plan = self.planner.generate_plan(task_id=tid, objective=objective, files=files)
            if family:
                plan.task_type = family  # le type choisi dans l'interface prime
        plan_duration_ms = (time.time() - plan_start) * 1000

        notify(f"Plan généré : Famille '{plan.task_type}' avec {len(plan.steps)} étapes.")
        journal.log_event(
            task_id=tid,
            agent="planner",
            action="plan_generated",
            duration_ms=plan_duration_ms,
            result={"task_type": plan.task_type, "steps_count": len(plan.steps)}
        )

        # 3. Exécution des étapes, vague par vague (les étapes indépendantes
        #    d'une même vague tournent en parallèle, dans la limite de MAX_PARALLEL_STEPS)
        waves = group_steps_in_waves(plan.steps)
        total_steps = len(plan.steps)
        report_path_str = ""
        final_output_text = ""
        steps_done = 0

        for wave in waves:
            # Vérification des limites avant chaque vague
            limits.steps_done = steps_done
            try:
                limits.check(action=f"vague_{'_'.join(str(s.id) for s in wave)}")
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

            standard = [s for s in wave if s.agent.lower().strip() != "writer"]
            writers = [s for s in wave if s.agent.lower().strip() == "writer"]

            for offset, step in enumerate(standard, start=1):
                notify(f"Étape {steps_done + offset}/{total_steps} : Exécution par l'agent '{step.agent.upper()}'...")
            workers = min(max(1, settings.max_parallel_steps), len(standard))
            if workers > 1:
                notify(f"{len(standard)} étapes indépendantes lancées en parallèle ({workers} à la fois).")
                parent_ctx = contextvars.copy_context()
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    # Chaque fil reçoit une copie du contexte de la tâche (ex. id pour les approbations)
                    list(pool.map(
                        lambda s: parent_ctx.copy().run(
                            self._execute_standard_step, step=s, plan=plan, memory=memory, notify=notify
                        ),
                        standard,
                    ))
            else:
                for step in standard:
                    self._execute_standard_step(step=step, plan=plan, memory=memory, notify=notify)
            steps_done += len(standard)

            # Étape de rédaction : boucle Rédacteur ↔ Critique
            if writers:
                self._ensure_document_facts(memory, notify)
            for step in writers:
                steps_done += 1
                notify(f"Étape {steps_done}/{total_steps} : Exécution par l'agent 'WRITER'...")
                final_output_text, report_file = self._execute_writer_with_critic(
                    step=step,
                    plan=plan,
                    memory=memory,
                    notify=notify
                )
                report_path_str = str(report_file)

        # Si aucun agent writer n'a été planifié, on génère quand même le rapport canonique
        if not report_path_str:
            self._ensure_document_facts(memory, notify)
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
        if getattr(memory, "files", None):
            context = {**(context or {}), "fichiers_fournis": memory.files}
        start_time = time.time()
        error_msg: Optional[str] = None
        try:
            agent = self.agent_factory(step.agent)
            output_text = agent.run(step.instruction, context=context)
        except Exception as exc:  # une étape en échec ne fait pas tomber toute la tâche
            error_msg = f"{type(exc).__name__} : {exc}"
            output_text = f"Étape {step.id} non réalisée ({error_msg})."
            notify(f"⚠️ L'étape {step.id} ({step.agent}) a échoué : {error_msg}. La tâche continue.")
        duration_ms = (time.time() - start_time) * 1000

        extracted_facts = self.runner._extract_facts_from_output(output_text)

        step_result = StepResult(
            step_id=step.id,
            agent=step.agent,
            success=error_msg is None,
            output_text=output_text,
            facts=extracted_facts,
            error=error_msg,
        )
        with self._memory_lock:
            memory.add_step_result(step_result)

        journal.log_event(
            task_id=plan.task_id,
            agent=step.agent,
            action=f"execute_step_{step.id}",
            duration_ms=duration_ms,
            result={"facts_found": len(extracted_facts), "success": error_msg is None},
            error=error_msg,
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
                previous_outputs=self._previous_outputs(memory),
                feedback=feedback
            )

            # 2. Évaluation par le Critique
            notify("Évaluation de la qualité et des sources par l'agent Critique...")
            critique: CriticEvaluation = self.critic.evaluate(
                instruction=step.instruction,
                output_text=current_report,
                available_facts=memory.get_facts(),
                reference_text=plan.objective + "\n" + "\n".join(self._previous_outputs(memory).values()),
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

            # Remarques seulement « d'avis » (pas de contrôle automatique en échec) :
            # une seule révision suffit, inutile de boucler sur l'opinion du modèle.
            avis_seulement = not critique.ok and not critique.bloquant and revision >= 1
            if critique.ok or revision >= max_revisions or avis_seulement:
                if critique.ok:
                    notify(f"Approbation du Critique validée avec succès (Score : {critique.score}/10).")
                elif critique.bloquant:
                    notify(f"Note qualité : {critique.score}/10 (contrôles automatiques en échec, rapport finalisé avec avertissement).")
                    # Honnêteté : le lecteur doit voir que le rapport n'a pas passé le contrôle
                    current_report = (
                        "> ⚠️ **Rapport non validé par le Critique** — à vérifier avant usage :\n"
                        + "\n".join(f"> - {p}" for p in critique.problemes[:5]) + "\n\n"
                        + current_report
                    )
                else:
                    notify(f"Contrôles automatiques réussis ; remarques du Critique ajoutées en fin de rapport (score {critique.score}/10).")
                    current_report += (
                        "\n\n> ℹ️ **Remarques du Critique (non bloquantes)** :\n"
                        + "\n".join(f"> - {p}" for p in critique.problemes[:5]) + "\n"
                    )
                if report_file and not critique.ok:
                    Path(report_file).write_text(current_report, encoding="utf-8")
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

    def _ensure_document_facts(self, memory: ShortTermMemory, notify: Callable[[str], None],
                               max_chunks_per_file: int = 8) -> None:
        """Garantit que le Rédacteur dispose de faits issus des fichiers fournis.

        Si les agents n'ont produit aucun fait sourcé pour un fichier (modèle qui n'a pas
        appelé l'outil, JSON invalide...), on extrait directement ses pages : le rapport
        s'appuie alors sur le texte réel des documents au lieu d'être inventé.
        """
        files = getattr(memory, "files", None) or []
        if not files:
            return
        from tools.documents import extract_document
        from orchestrator.plan_models import ConfidenceLevel, SourceType

        cited = {Path(f.source_name).name.lower() for f in memory.get_facts()}
        added = 0
        for file_path in files:
            name = Path(file_path).name
            if name.lower() in cited:
                continue
            try:
                chunks = extract_document(file_path)[:max_chunks_per_file]
            except Exception as exc:
                notify(f"⚠️ Lecture directe impossible de {name} : {exc}")
                continue
            for chunk in chunks:
                text = " ".join(chunk.content.split())
                if not text:
                    continue
                memory.add_fact(Fact(
                    assertion=text[:700],
                    source_type=SourceType.DOCUMENT,
                    source_name=name,
                    page_or_section=f"Page {chunk.page_number}",
                    exact_quote=text[:200],
                    confidence=ConfidenceLevel.MEDIUM,
                ))
                added += 1
        if added:
            notify(f"Extraction directe de {added} passage(s) des documents fournis pour sourcer le rapport.")

    @staticmethod
    def _previous_outputs(memory: ShortTermMemory, max_chars: int = 3000) -> Dict[str, str]:
        """Textes produits par les étapes précédentes (analyses, calculs...) pour le Rédacteur.
        Les sorties purement JSON (faits) sont déjà transmises via la liste des faits."""
        outputs: Dict[str, str] = {}
        for step_id, res in sorted(memory.get_all_step_results().items()):
            text = (res.output_text or "").strip()
            if not text or res.agent.lower() == "writer" or text.startswith("{\"facts\""):
                continue
            outputs[f"etape_{step_id}_{res.agent}"] = text[:max_chars]
        return outputs

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
                partial_body += f"- [{i}] {f.assertion} *(Source : {f.source_name})*\n"
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
