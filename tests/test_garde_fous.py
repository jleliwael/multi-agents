"""Garde-fous contre les inventions, ajoutés après les essais réels avec un modèle local."""

import json
import unittest

from agents.critic import CriticAgent, unsupported_numbers
from agents.writer import clean_report_body
from llm.ollama_llm import OllamaResponse
from orchestrator.plan_models import Fact
from scripts.evaluate import contains, normalize, score_task
from tests.conftest import MockOllamaLLM


class TestChiffresNonSources(unittest.TestCase):
    SOURCE = "Le chiffre d'affaires a atteint 45 millions d'euros, +12 %. R&D : 8,5 millions. Total 1 150 000."

    def test_invented_number_is_flagged(self):
        report = "## Réponse\nLe CA 2025 est de 123 456 789 € [1].\n## Sources et Références\n| 1 | 77 |"
        self.assertEqual(unsupported_numbers(report, self.SOURCE), ["123456789"])

    def test_real_numbers_years_and_formats_pass(self):
        report = ("# Rapport du 19/11/2026\n## 1. Résumé\n### 3.1 Détail\nCA de 45 M€ en 2025 (+12 %) [1], "
                  "R&D 8,5 M€ [2], total 1150000 €, 3 offres.\n1. premier point")
        self.assertEqual(unsupported_numbers(report, self.SOURCE), [])

    def test_critic_blocks_invented_number_even_if_llm_approves(self):
        llm = MockOllamaLLM(responses_sequence=[{"message": {"role": "assistant", "content": json.dumps(
            {"ok": True, "problemes": [], "suggestions": [], "score": 9.5})}}])
        fact = Fact(assertion="CA de 45 millions", source_name="a.pdf", exact_quote="45 millions")
        ev = CriticAgent(llm_client=llm).evaluate("Donner le CA", "Le CA est de 99 millions d'euros [1], selon le rapport annuel.", [fact])
        self.assertFalse(ev.ok)
        self.assertTrue(ev.bloquant)
        self.assertIn("99", ev.problemes[0])


class TestNettoyageRapport(unittest.TestCase):
    def test_removes_echoed_prompt_and_fake_sources(self):
        body = ("```markdown\n# Titre\n## 2. Analyse des sources de revenus\ntexte [1]\n"
                "[1] Fait (Source: a.pdf, Page 1 - Citation: « x »)\n"
                "## 5. Bibliographie et Sources\n| inventé |\nFAITS CERTIFIÉS DISPONIBLES : ...\n```")
        cleaned = clean_report_body(body)
        self.assertIn("Analyse des sources de revenus", cleaned)
        self.assertNotIn("inventé", cleaned)
        self.assertNotIn("Citation", cleaned)
        self.assertNotIn("```", cleaned)


class TestAppelsOutilsEnTexte(unittest.TestCase):
    def test_only_first_call_is_kept(self):
        content = ('[{"name":"read_document_pages","arguments":{"filepath":"a.pdf"}}]\n'
                   '[Contexte de la réponse : {"content":"Chiffre inventé : 12 000 000 €"}]\n'
                   '[{"name":"memory_search","arguments":{"query":"x"}}]')
        resp = OllamaResponse({"role": "assistant", "content": content}, {})
        self.assertEqual([c["function"]["name"] for c in resp.tool_calls], ["read_document_pages"])
        self.assertTrue(resp.tool_calls_from_text)

    def test_facts_json_is_not_a_tool_call(self):
        resp = OllamaResponse({"role": "assistant", "content": '{"facts": [{"assertion": "x"}]}'}, {})
        self.assertFalse(resp.has_tool_calls())

    def test_think_block_is_removed(self):
        resp = OllamaResponse({"role": "assistant", "content": "<think>je réfléchis</think>Réponse"}, {})
        self.assertEqual(resp.content, "Réponse")


class TestNotationEvaluation(unittest.TestCase):
    def test_matching_ignores_accents_and_number_spaces(self):
        text = normalize("Le total est de 1 150 000 €, à l'Énergie près")
        self.assertTrue(contains(text, "1150000"))
        self.assertTrue(contains(text, "energie"))

    def test_score_task(self):
        task = {"attendu": {"doit_contenir": [["45"], ["page 1", "p.1"]], "sources_min": 1,
                            "sources_attendues": ["exemple.pdf"]}}
        run = {"status": "COMPLETED", "final_output": "Le CA est de 45 M€ (page 1) [1].", "duree_s": 10,
               "facts": [{"source_name": "exemple.pdf"}]}
        ev = score_task(task, run)
        self.assertTrue(ev["reussie"])
        self.assertEqual(ev["score"], 100.0)
        run["final_output"] = "Le CA est de 45 M€ [3]."
        ev = score_task(task, run)
        self.assertFalse(ev["reussie"])
        self.assertEqual(ev["citations_inventees"], [3])


if __name__ == "__main__":
    unittest.main()
