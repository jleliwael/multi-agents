"""Génération des documents de test dans tests/fixtures/."""

from pathlib import Path
import fitz
import docx
import openpyxl

FIXTURES_DIR = Path("C:/Users/user/Desktop/multi-agents/tests/fixtures")
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

# 1. Génération de exemple.pdf (3 pages de rapport d'entreprise)
pdf_path = FIXTURES_DIR / "exemple.pdf"
doc_pdf = fitz.open()

# Page 1
p1 = doc_pdf.new_page()
p1.insert_text((50, 80), "RAPPORT ANNUEL D'ACTIVITE - EXERCICE 2025\n\nPage 1 : Resume Executif\nLe chiffre d'affaires consolide a atteint 45 millions d'euros, enregistrant une croissance annuelle de 12% par rapport a 2024.\nL'activite logiciels represente desormais 65% des revenus globaux de l'entreprise.", fontsize=11)

# Page 2
p2 = doc_pdf.new_page()
p2.insert_text((50, 80), "RAPPORT ANNUEL D'ACTIVITE - EXERCICE 2025\n\nPage 2 : Analyse Operationnelle et R&D\nLes investissements en recherche et developpement se sont eleves a 8,5 millions d'euros.\nUne nouvelle infrastructure d'IA locale a ete deployee, reduisant les couts d'inference cloud de 40%.\nLe taux de satisfaction client atteint 94,2% en fin d'exercice.", fontsize=11)

# Page 3
p3 = doc_pdf.new_page()
p3.insert_text((50, 80), "RAPPORT ANNUEL D'ACTIVITE - EXERCICE 2025\n\nPage 3 : Perspectives et Risques 2026\nPour 2026, l'objectif principal est l'expansion internationale sur le marche europeen.\nLe plafond des investissements materiels est fixe a 5 millions d'euros.\nLe principal facteur de risque identifie concerne la volatilite des couts energetiques.", fontsize=11)

doc_pdf.save(str(pdf_path))
doc_pdf.close()
print(f"[OK] PDF cree : {pdf_path.name}")

# 2. Génération de exemple.docx
docx_path = FIXTURES_DIR / "exemple.docx"
doc_word = docx.Document()
doc_word.add_heading("Compte-Rendu de Réunion Stratégique", level=1)
doc_word.add_paragraph("Participants : Direction Générale, Responsable R&D, Responsable Sécurité.")
doc_word.add_paragraph("Décision 1 : Tous les agents IA doivent obligatoirement s'exécuter en local sans envoi de données à l'extérieur.")
doc_word.add_paragraph("Décision 2 : L'approbation humaine est impérative avant toute opération de paiement ou de suppression de données.")
doc_word.save(str(docx_path))
print(f"[OK] DOCX cree : {docx_path.name}")

# 3. Génération de exemple.xlsx
xlsx_path = FIXTURES_DIR / "exemple.xlsx"
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Ventes_2025"
ws.append(["Mois", "Chiffre d'Affaires", "Charges", "Marge Nette"])
ws.append(["Janvier", 350000, 210000, 140000])
ws.append(["Fevrier", 380000, 220000, 160000])
ws.append(["Mars", 420000, 230000, 190000])
wb.save(str(xlsx_path))
print(f"[OK] XLSX cree : {xlsx_path.name}")
