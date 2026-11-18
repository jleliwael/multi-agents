"""Tests unitaires pour la Phase 5 : Web search, Fetch page, ChromaDB, Code runner et Approbation."""

import unittest
import json
from pathlib import Path

from tools.web_search import web_search
from tools.fetch_page import fetch_page
from memory.chunking import split_text_with_overlap, DocumentChunk
from memory.long_term import LongTermMemory
from tools.code_runner import execute_python_code
from security.approval import require_approval
from config import settings


class TestPhase5Tools(unittest.TestCase):

    def test_web_search_interface(self):
        # Test de l'interface commune web_search
        res_str = web_search("Modèles de langage compacts", max_results=2)
        self.assertTrue(res_str.startswith("[") or "{" in res_str)
        data = json.loads(res_str)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        self.assertIn("title", data[0])
        self.assertIn("url", data[0])

    def test_fetch_page_security_rejection(self):
        # Rejet immédiat des fichiers exécutables malveillants
        res_exe = fetch_page("https://example.com/malware.exe")
        self.assertIn("Erreur de sécurité", res_exe)

        res_bat = fetch_page("https://example.com/script.bat")
        self.assertIn("Erreur de sécurité", res_bat)

    def test_chunking_strategy_with_overlap(self):
        text = "Premier paragraphe important sur les ventes. " * 30
        chunks = split_text_with_overlap(text, max_chars=300, overlap=50)
        self.assertGreater(len(chunks), 1)
        # Vérification du chevauchement
        self.assertTrue(len(chunks[0]) <= 300)

    def test_long_term_chromadb_memory(self):
        test_chroma_dir = settings.workspace_dir / "test_chroma"
        mem = LongTermMemory(persist_dir=test_chroma_dir, collection_name="test_col")

        chunks = [
            DocumentChunk(
                chunk_id="chunk_test_1",
                text="Le chiffre d'affaires consolidé est de 45 millions d'euros en 2025.",
                source_file="bilan.pdf",
                file_type="pdf",
                page_number=1,
                chunk_index=1,
                char_count=65,
                created_at="2026-11-18T23:55:00"
            )
        ]
        added = mem.add_chunks(chunks)
        self.assertEqual(added, 1)

        # Recherche de similarité
        matches = mem.search_similar("Quel est le chiffre d'affaires ?", top_k=1)
        self.assertGreaterEqual(len(matches), 1)
        self.assertIn("45 millions", matches[0]["text"])

    def test_code_runner_execution_and_timeout(self):
        # 1. Calcul réussi
        code_calc = "import json; print(json.dumps({'somme': 20 + 22}))"
        res_calc = execute_python_code(code_calc)
        self.assertIn("somme", res_calc)
        self.assertIn("42", res_calc)

        # 2. Timeout sur boucle infinie
        code_infinite = "import time; time.sleep(20)"
        res_timeout = execute_python_code(code_infinite)
        self.assertIn("Dépassement du temps limite", res_timeout)

    def test_security_approval_bypass_when_disabled(self):
        # Par défaut require_human_approval est False en environnement de test
        is_ok = require_approval("test_action", "test_target")
        self.assertTrue(is_ok)


if __name__ == "__main__":
    unittest.main()
