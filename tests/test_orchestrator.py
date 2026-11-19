"""Tests unitaires pour la Phase 4b : Planificateur, Fallback, Tri topologique et Orchestrateur."""

import unittest
import json
from pathlib import Path

from orchestrator.plan_models import Plan, Step, Fact, SourceType, ConfidenceLevel
from orchestrator.fallback import detect_task_family, get_fallback_plan
from orchestrator.runner import topological_sort_steps, PlanRunner
from agents.planner import PlannerAgent
from memory.short_term import ShortTermMemory
from orchestrator.orchestrator import Orchestrator
from tests.conftest import MockOllamaLLM
from logging_.journal import journal
from agents.critic import CriticAgent
from agents.writer import WriterAgent
from storage.repository import TaskRepository
from orchestrator.orchestrator import group_steps_in_waves
import tempfile
import threading
import time


class TestOrchestration(unittest.TestCase):

    def test_topological_sort_linear_and_branching(self):
        # 1. Chaîne linéaire : 3 dépend de 2, 2 dépend de 1
        steps_linear = [
            Step(id=3, agent="writer", instruction="Rédiger", depends_on=[2]),
            Step(id=1, agent="reader", instruction="Lire", depends_on=[]),
            Step(id=2, agent="analyst", instruction="Analyser", depends_on=[1]),
        ]
        sorted_steps = topological_sort_steps(steps_linear)
        self.assertEqual([s.id for s in sorted_steps], [1, 2, 3])

        # 2. Branchement parallèle : 4 dépend de [2, 3], 2 et 3 dépendent de 1
        steps_branching = [
            Step(id=4, agent="writer", instruction="Synthétiser", depends_on=[2, 3]),
            Step(id=2, agent="analyst", instruction="Analyser A", depends_on=[1]),
            Step(id=3, agent="coder", instruction="Calculer B", depends_on=[1]),
            Step(id=1, agent="reader", instruction="Extraire", depends_on=[]),
        ]
        sorted_branching = topological_sort_steps(steps_branching)
        ids = [s.id for s in sorted_branching]
        self.assertEqual(ids[0], 1)
        self.assertEqual(ids[-1], 4)
        self.assertIn(ids[1], [2, 3])
        self.assertIn(ids[2], [2, 3])

    def test_topological_sort_cycle_and_invalid_deps(self):
        # Cycle : 1 dépend de 2 et 2 dépend de 1
        cyclic_steps = [
            Step(id=1, agent="reader", instruction="A", depends_on=[2]),
            Step(id=2, agent="writer", instruction="B", depends_on=[1]),
        ]
        with self.assertRaises(ValueError):
            topological_sort_steps(cyclic_steps)

        # Dépendance inexistante : 1 dépend de 99
        invalid_dep_steps = [
            Step(id=1, agent="reader", instruction="A", depends_on=[99]),
        ]
        with self.assertRaises(ValueError):
            topological_sort_steps(invalid_dep_steps)

    def test_fallback_task_families_detection(self):
        # Synthèse
        plan_synth = get_fallback_plan("t1", "Analyser les documents PDF et faire un résumé")
        self.assertEqual(plan_synth.task_type, "synthese")
        self.assertEqual([s.agent for s in plan_synth.steps], ["reader", "writer"])

        # Veille
        plan_veille = get_fallback_plan("t2", "Faire une veille sur le web concernant les IA en 2026")
        self.assertEqual(plan_veille.task_type, "veille")
        self.assertEqual([s.agent for s in plan_veille.steps], ["researcher", "writer"])

        # Comparatif
        plan_comp = get_fallback_plan("t3", "Faire un benchmark comparatif de solutions A vs B")
        self.assertEqual(plan_comp.task_type, "comparatif")
        self.assertEqual([s.agent for s in plan_comp.steps], ["researcher", "analyst", "writer"])

    def test_planner_valid_json_generation(self):
        valid_json = json.dumps({
            "task_id": "task-test-01",
            "objective": "Test de plan valide",
            "task_type": "synthese",
            "steps": [
                {"id": 1, "agent": "reader", "instruction": "Lire", "depends_on": []},
                {"id": 2, "agent": "writer", "instruction": "Écrire", "depends_on": [1]}
            ]
        })
        mock_llm = MockOllamaLLM(responses_sequence=[
            {"message": {"role": "assistant", "content": valid_json}}
        ])
        planner = PlannerAgent(llm_client=mock_llm)
        plan = planner.generate_plan("task-test-01", "Test de plan valide")

        self.assertEqual(plan.task_id, "task-test-01")
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].agent, "reader")

    def test_planner_broken_json_triggers_fallback(self):
        # Le LLM renvoie du texte incohérent à chaque tentative
        mock_llm = MockOllamaLLM(responses_sequence=[
            {"message": {"role": "assistant", "content": "Je ne peux pas répondre en JSON."}},
            {"message": {"role": "assistant", "content": "Toujours pas de JSON ici."}},
            {"message": {"role": "assistant", "content": "{json_invalide_total}"}},
        ])
        planner = PlannerAgent(llm_client=mock_llm)
        plan = planner.generate_plan("task-fail-01", "Veille technologique sur le web")

        # Doit déclencher le fallback veille
        self.assertEqual(plan.task_type, "veille")
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].agent, "researcher")
        self.assertEqual(plan.steps[1].agent, "writer")

    def test_short_term_memory_and_orchestrator(self):
        # Simulation d'un agent renvoyant un fait structuré
        class DummyAgent:
            def __init__(self, name: str):
                self.name = name

            def run(self, task: str, context: dict | None = None) -> str:
                if self.name == "reader":
                    return json.dumps({
                        "facts": [
                            {
                                "assertion": "Le chiffre d'affaires 2025 est de 45 M€.",
                                "source_type": "document",
                                "source_name": "bilan.pdf",
                                "page_or_section": "Page 1",
                                "exact_quote": "Chiffre d'affaires : 45 M€",
                                "confidence": "haute"
                            }
                        ]
                    })
                return f"Rapport final rédigé par {self.name} basé sur les faits."

        # Valid plan
        valid_json = json.dumps({
            "task_id": "task-flow-01",
            "objective": "Synthèse bilan.pdf",
            "task_type": "synthese",
            "steps": [
                {"id": 1, "agent": "reader", "instruction": "Extraire faits", "depends_on": []},
                {"id": 2, "agent": "writer", "instruction": "Rédiger rapport", "depends_on": [1]}
            ]
        })
        mock_llm = MockOllamaLLM(responses_sequence=[
            {"message": {"role": "assistant", "content": valid_json}}
        ])
        planner = PlannerAgent(llm_client=mock_llm)
        # Critique et Rédacteur simulés : le test ne doit jamais appeler un vrai modèle
        orchestrator = Orchestrator(
            planner=planner,
            critic=CriticAgent(llm_client=MockOllamaLLM()),
            writer=WriterAgent(llm_client=MockOllamaLLM()),
            repository=TaskRepository(db_path=Path(tempfile.mkdtemp()) / "test.db"),
            agent_factory=lambda name: DummyAgent(name),
        )

        result = orchestrator.run(objective="Synthèse bilan.pdf", task_id="task-flow-01")

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(len(result["facts"]), 1)
        self.assertEqual(result["facts"][0]["assertion"], "Le chiffre d'affaires 2025 est de 45 M€.")
        self.assertIn("Sources et Références", result["final_output"])


    def _orchestrator(self, plan_json: str, factory):
        return Orchestrator(
            planner=PlannerAgent(llm_client=MockOllamaLLM(responses_sequence=[
                {"message": {"role": "assistant", "content": plan_json}}
            ])),
            critic=CriticAgent(llm_client=MockOllamaLLM()),
            writer=WriterAgent(llm_client=MockOllamaLLM()),
            repository=TaskRepository(db_path=Path(tempfile.mkdtemp()) / "test.db"),
            agent_factory=factory,
        )

    def test_waves_group_independent_steps(self):
        steps = [
            Step(id=1, agent="reader", instruction="Lire A", depends_on=[]),
            Step(id=2, agent="researcher", instruction="Chercher B", depends_on=[]),
            Step(id=3, agent="analyst", instruction="Comparer", depends_on=[1, 2]),
            Step(id=4, agent="writer", instruction="Rédiger", depends_on=[3]),
        ]
        waves = group_steps_in_waves(steps)
        self.assertEqual([[s.id for s in w] for w in waves], [[1, 2], [3], [4]])

    def test_independent_steps_run_in_parallel(self):
        active, peak, lock = [0], [0], threading.Lock()

        class SlowAgent:
            def __init__(self, name): self.name = name
            def run(self, task, context=None):
                with lock:
                    active[0] += 1
                    peak[0] = max(peak[0], active[0])
                time.sleep(0.3)
                with lock:
                    active[0] -= 1
                return "ok"

        plan = json.dumps({"task_id": "t-par", "objective": "x", "task_type": "comparatif", "steps": [
            {"id": 1, "agent": "reader", "instruction": "a", "depends_on": []},
            {"id": 2, "agent": "researcher", "instruction": "b", "depends_on": []},
            {"id": 3, "agent": "writer", "instruction": "c", "depends_on": [1, 2]},
        ]})
        result = self._orchestrator(plan, SlowAgent).run(objective="x", task_id="t-par")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(peak[0], 2, "les deux étapes indépendantes doivent tourner en même temps")

    def test_failing_step_does_not_stop_task(self):
        class FlakyAgent:
            def __init__(self, name): self.name = name
            def run(self, task, context=None):
                if self.name == "reader":
                    raise RuntimeError("document illisible")
                return "analyse faite"

        plan = json.dumps({"task_id": "t-err", "objective": "x", "task_type": "synthese", "steps": [
            {"id": 1, "agent": "reader", "instruction": "a", "depends_on": []},
            {"id": 2, "agent": "analyst", "instruction": "b", "depends_on": [1]},
            {"id": 3, "agent": "writer", "instruction": "c", "depends_on": [2]},
        ]})
        messages = []
        result = self._orchestrator(plan, FlakyAgent).run(objective="x", task_id="t-err", on_progress=messages.append)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(any("a échoué" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
