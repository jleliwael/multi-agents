"""Crée les documents de test supplémentaires utilisés par le jeu d'évaluation (Phase 7).

    python scripts/_create_eval_fixtures.py

- tests/fixtures/offres_logiciels.docx : 3 offres de logiciels de comptabilité à comparer
- tests/fixtures/market_report_en.pdf  : court rapport en anglais (tâches de traduction)
Le contenu est fixe pour que l'évaluation soit reproductible.
"""

from pathlib import Path

import docx
import fitz  # PyMuPDF

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def create_offres_docx(path: Path) -> None:
    doc = docx.Document()
    doc.add_heading("Comparatif des offres de logiciels de comptabilité", level=1)
    offres = [
        ("Offre A — ComptaSimple", "29 € par mois", "3 utilisateurs", "Support par e-mail uniquement",
         "Pas d'hébergement local : données stockées dans le cloud."),
        ("Offre B — GestPro", "49 € par mois", "10 utilisateurs", "Support téléphonique 5j/7",
         "Hébergement local possible sur le serveur de l'entreprise."),
        ("Offre C — LibreCompta", "Gratuit (open source)", "Utilisateurs illimités", "Support communautaire",
         "Installation locale obligatoire, maintenance à la charge de l'entreprise."),
    ]
    for titre, prix, users, support, hebergement in offres:
        doc.add_heading(titre, level=2)
        doc.add_paragraph(f"Prix : {prix}.")
        doc.add_paragraph(f"Nombre d'utilisateurs inclus : {users}.")
        doc.add_paragraph(f"Support : {support}.")
        doc.add_paragraph(f"Hébergement : {hebergement}")
    doc.add_paragraph(
        "Contrainte interne : la décision de réunion impose que les données restent en local."
    )
    doc.save(str(path))


def create_english_pdf(path: Path) -> None:
    pdf = fitz.open()
    pages = [
        "MARKET REPORT 2026 - LOCAL AI ASSISTANTS\n"
        "Page 1: Summary\n"
        "The market for local AI assistants grew by 35% in 2025.\n"
        "Data privacy is cited by 78% of companies as the main reason to run AI on-premises.",
        "MARKET REPORT 2026 - LOCAL AI ASSISTANTS\n"
        "Page 2: Outlook\n"
        "Small open models (7B to 14B parameters) now run on consumer GPUs with 6 to 12 GB of memory.\n"
        "The main barrier remains the lack of in-house technical skills.",
    ]
    for text in pages:
        page = pdf.new_page()
        page.insert_text((50, 72), text, fontsize=11)
    pdf.save(str(path))


if __name__ == "__main__":
    FIXTURES.mkdir(parents=True, exist_ok=True)
    create_offres_docx(FIXTURES / "offres_logiciels.docx")
    create_english_pdf(FIXTURES / "market_report_en.pdf")
    print("Documents créés dans", FIXTURES)
