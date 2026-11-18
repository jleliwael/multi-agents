"""Tests unitaires pour la Phase 4c : Critique, Citations, Rédacteur et SQLite."""

import unittest
from pathlib import Path
import json

from orchestrator.plan_models import Fact, SourceType, ConfidenceLevel
from tools.citations import CitationsManager
from agents.critic import CriticAgent
from agents.writer import WriterAgent
from storage.models import TaskRecord
from storage.repository import TaskRepository
from tests.conftest import MockOllamaLLM
from config import settings


class TestCriticAndStorage(unittest.TestCase):

    def setUp(self):
        self.sample_facts = [
            Fact(
                assertion="Le chiffre d'affaires consolidé s'élève à 45 M€.",
                source_type=SourceType.DOCUMENT,
                source_name="bilan_2025.pdf",
                page_or_section="Page 1",
                exact_quote="Le chiffre d'affaires s'élève à 45 M€",
                confidence=ConfidenceLevel.HIGH
            ),
            Fact(
                assertion="Les coûts d'inférence ont diminué de 40 %.",
                source_type=SourceType.DOCUMENT,
                source_name="bilan_2025.pdf",
                page_or_section="Page 2",
                exact_quote="coûts d'inférence réduits de 40 %",
                confidence=ConfidenceLevel.HIGH
            )
        ]

    def test_citations_manager_build_and_verify(self):
        sources_md, indexed = CitationsManager.build_sources_section(self.sample_facts)
        self.assertIn("[1]", sources_md)
        self.assertIn("[2]", sources_md)
        self.assertIn("bilan_2025.pdf", sources_md)

        # Vérification d'un texte avec citations valides
        valid_text = "Selon le rapport, le CA atteint 45 M€ [1] et les coûts baissent de 40% [2]."
        res_valid = CitationsManager.verify_text_citations(valid_text, total_sources=2)
        self.assertTrue(res_valid["is_valid"])
        self.assertEqual(res_valid["cited_indices"], [1, 2])

        # Vérification d'un texte avec citation hors borne [9]
        invalid_text = "Le CA atteint 45 M€ [9]."
        res_invalid = CitationsManager.verify_text_citations(invalid_text, total_sources=2)
        self.assertFalse(res_invalid["is_valid"])
        self.assertIn(9, res_invalid["invalid_indices"])

    def test_critic_agent_catches_invalid_citations(self):
        critic = CriticAgent()
        bad_text = "Le chiffre d'affaires explose à 100 M€ sans aucune source valide [99]."
        critique = critic.evaluate(
            instruction="Résumer le bilan",
            output_text=bad_text,
            available_facts=self.sample_facts
        )
        self.assertFalse(critique.ok)
        self.assertTrue(any("inexistant" in p for p in critique.problemes))

    def test_writer_agent_creates_report_file(self):
        writer = WriterAgent()
        report_content, report_path = writer.write_report(
            task_id="test-write-01",
            objective="Synthèse annuelle",
            task_type="synthese",
            facts=self.sample_facts
        )
        self.assertTrue(report_path.exists())
        self.assertIn("## Sources et Références", report_content)
        self.assertIn("bilan_2025.pdf", report_content)

    def test_sqlite_storage_repository(self):
        # Base temporaire dans workspace
        test_db = settings.workspace_dir / "test_storage.db"
        repo = TaskRepository(db_path=test_db)

        record = TaskRecord(
            task_id="task-sql-01",
            objective="Objectif de test SQLite",
            family="synthese",
            plan_json=json.dumps({"steps": []}),
            status="COMPLETED",
            duration_ms=1250.5,
            sources_count=2,
            report_path=str(settings.reports_dir / "test_report.md"),
            created_at="2026-11-18T23:40:00"
        )
        repo.save_task(record)

        fetched = repo.get_task("task-sql-01")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.objective, "Objectif de test SQLite")
        self.assertEqual(fetched.sources_count, 2)
        self.assertEqual(fetched.status, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
