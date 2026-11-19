"""Tests Phase 9 : registre d'agents YAML, option Claude avec repli, export Word, rapport des avis."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agents.registry as registry
from llm.claude_llm import FallbackLLM, make_reasoning_llm
from llm.ollama_llm import OllamaLLM, OllamaResponse
from ui.export import markdown_to_docx


class TestRegistry(unittest.TestCase):
    def test_builtin_agents_have_their_tools(self):
        self.assertIn("web_search", registry.create_agent("researcher").tools)
        self.assertIn("code_runner", registry.create_agent("coder").tools)
        self.assertIn("memory_search", registry.create_agent("reader").tools)

    def test_yaml_agent_is_loaded(self):
        agent = registry.create_agent("translator")
        self.assertIn("Traducteur", agent.system_prompt)
        self.assertEqual(agent.tools, ["read_document_pages", "fetch_page"])
        self.assertIn("translator", registry.available_agent_names())

    def test_new_yaml_file_adds_an_agent(self):
        folder = Path(tempfile.mkdtemp())
        (folder / "comptable.yaml").write_text(
            "name: comptable\nrole: Comptable\ntools: [calculator]\nprompt: Tu es le comptable.\n", encoding="utf-8")
        (folder / "casse.yaml").write_text("pas: [du yaml valide", encoding="utf-8")
        with mock.patch.object(registry, "DEFINITIONS_DIR", folder):
            agent = registry.create_agent("comptable")
        self.assertEqual(agent.tools, ["calculator"])
        self.assertEqual(agent.system_prompt, "Tu es le comptable.")

    def test_unknown_agent_gets_generic_tools(self):
        agent = registry.create_agent("inconnu")
        self.assertEqual(agent.name, "inconnu")
        self.assertIn("read_document_pages", agent.tools)


class TestClaudeOption(unittest.TestCase):
    def test_without_key_stays_local(self):
        with mock.patch("llm.claude_llm.settings") as s:
            s.anthropic_api_key = ""
            s.model_planner = "qwen3:14b"
            self.assertIsInstance(make_reasoning_llm(), OllamaLLM)

    def test_fallback_to_ollama_on_error(self):
        class Broken:
            model = "claude"
            def chat(self, **kw):
                raise ConnectionError("quota")

        class Local:
            def chat(self, **kw):
                return OllamaResponse({"role": "assistant", "content": "local"}, {})

        self.assertEqual(FallbackLLM(Broken(), Local()).chat(messages=[]).content, "local")


class TestExportAndFeedback(unittest.TestCase):
    def test_markdown_to_docx(self):
        md = "# Titre\n\n**Gras** et [lien](https://exemple.org)\n\n- point\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        data = markdown_to_docx(md, "Test")
        self.assertTrue(data.startswith(b"PK"), "un .docx est une archive zip")

    def test_feedback_report(self):
        from scripts.feedback_report import build_report
        from storage.repository import FeedbackRepository
        repo = FeedbackRepository(db_path=Path(tempfile.mkdtemp()) / "fb.db")
        repo.add("t1", -1, "Résumé", "trop vague")
        repo.add("t1", 1, "rapport", "")
        text = build_report(repo.list(), tasks_by_id={"t1": {"family": "synthese", "objective": "obj"}})
        self.assertIn("trop vague", text)
        self.assertIn("synthese", text)


if __name__ == "__main__":
    unittest.main()
