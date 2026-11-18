"""Tests unitaires pour la boîte à outils fondamentale."""

import unittest
from pathlib import Path
from tools.calculator import calculate
from tools.datetime_tool import get_current_datetime, calculate_date_delta
from tools.files import read_file, write_file, list_files
from tools.documents import extract_document, read_document_pages
from tools.registry import registry
from config import settings


class TestTools(unittest.TestCase):

    def test_calculator_basic_operations(self):
        self.assertEqual(calculate("15 + 27"), "42")
        self.assertEqual(calculate("100 * 1.20"), "120")
        self.assertEqual(calculate("2 ** 8"), "256")
        self.assertEqual(calculate("sqrt(49) + 3"), "10")

    def test_calculator_security_no_eval(self):
        # Vérification qu'aucune injection Python ou appel malveillant n'est possible
        res = calculate("__import__('os').system('dir')")
        self.assertTrue("Erreur" in res or "invalide" in res)

        div_zero = calculate("10 / 0")
        self.assertIn("Division par zéro", div_zero)

    def test_datetime_tool(self):
        dt_res = get_current_datetime()
        self.assertIn("Date et heure actuelles", dt_res)

        delta_res = calculate_date_delta(10)
        self.assertIn("10 jours dans le futur", delta_res)

    def test_files_security_confinement(self):
        # Écriture autorisée dans data/workspace
        write_res = write_file("test_unit.txt", "Contenu de test")
        self.assertIn("Succès", write_res)

        # Vérification du fichier créé
        written_path = settings.workspace_dir / "test_unit.txt"
        self.assertTrue(written_path.exists())

        # Lecture autorisée
        read_res = read_file(str(written_path))
        self.assertEqual(read_res, "Contenu de test")

        # Tentative d'écriture interdite hors de data/workspace (ex: à la racine)
        forbidden_write = write_file("C:/Windows/System32/hacked.txt", "bad")
        self.assertIn("Erreur de sécurité", forbidden_write)

    def test_documents_extractor_pdf(self):
        pdf_fixture = Path("tests/fixtures/exemple.pdf")
        self.assertTrue(pdf_fixture.exists(), "La fixture exemple.pdf doit exister")

        chunks = extract_document(str(pdf_fixture))
        self.assertEqual(len(chunks), 3, "Le PDF exemple contient 3 pages")
        self.assertEqual(chunks[0].page_number, 1)
        self.assertIn("45 millions d'euros", chunks[0].content)
        self.assertEqual(chunks[1].page_number, 2)
        self.assertIn("8,5 millions d'euros", chunks[1].content)
        self.assertEqual(chunks[2].page_number, 3)
        self.assertIn("expansion internationale", chunks[2].content)

    def test_documents_extractor_docx(self):
        docx_fixture = Path("tests/fixtures/exemple.docx")
        self.assertTrue(docx_fixture.exists())

        chunks = extract_document(str(docx_fixture))
        self.assertGreaterEqual(len(chunks), 1)
        self.assertIn("Compte-Rendu de Réunion", chunks[0].content)

    def test_documents_extractor_xlsx(self):
        xlsx_fixture = Path("tests/fixtures/exemple.xlsx")
        self.assertTrue(xlsx_fixture.exists())

        chunks = extract_document(str(xlsx_fixture))
        self.assertGreaterEqual(len(chunks), 1)
        self.assertIn("Ventes_2025", chunks[0].content)
        self.assertIn("Chiffre d'Affaires", chunks[0].content)

    def test_tool_registry_introspection(self):
        schema = registry.get_tool("calculator").schema
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "calculator")
        self.assertIn("expression", schema["function"]["parameters"]["properties"])


if __name__ == "__main__":
    unittest.main()
