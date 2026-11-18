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
        orchestrator = Orchestrator(planner=planner, agent_factory=lambda name: DummyAgent(name))

        result = orchestrator.run(objective="Synthèse bilan.pdf", task_id="task-flow-01")

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(len(result["facts"]), 1)
        self.assertEqual(result["facts"][0]["assertion"], "Le chiffre d'affaires 2025 est de 45 M€.")
        self.assertIn("Rapport final rédigé par writer", result["final_output"])


if __name__ == "__main__":
    unittest.main()
