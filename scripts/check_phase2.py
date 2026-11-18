"""Script de vérification pour la Phase 2 (Conception de l'architecture).

Contrôle la présence et la complétude des fiches agents, prompts, templates, mémoire et architecture.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

AGENTS_DOC = BASE_DIR / "docs" / "agents.md"
MEMOIRE_DOC = BASE_DIR / "docs" / "memoire.md"
ARCHI_DOC = BASE_DIR / "docs" / "architecture.md"

PROMPTS_DIR = BASE_DIR / "agents" / "prompts"
TEMPLATES_DIR = BASE_DIR / "agents" / "templates"

EXPECTED_PROMPTS = [
    "planner.md",
    "researcher.md",
    "reader.md",
    "analyst.md",
    "coder.md",
    "writer.md",
    "critic.md",
]

EXPECTED_TEMPLATES = [
    "synthese.md",
    "veille.md",
    "comparatif.md",
]


def test_phase2() -> None:
    print("=== Contrôle de la Phase 2 : Architecture et Agents ===")

    # 1. Vérification des documents généraux
    for doc in [AGENTS_DOC, MEMOIRE_DOC, ARCHI_DOC]:
        assert doc.exists(), f"Fichier manquant : {doc}"
        assert doc.stat().st_size > 500, f"Fichier trop court : {doc}"
        print(f"[OK] Document d'architecture : {doc.name}")

    # 2. Vérification des prompts des 7 agents
    for p_name in EXPECTED_PROMPTS:
        p_path = PROMPTS_DIR / p_name
        assert p_path.exists(), f"Prompt manquant : {p_name}"
        content = p_path.read_text(encoding="utf-8")
        assert "Règles" in content or "Règles Strictes" in content, f"Règles absentes dans {p_name}"
        print(f"[OK] Prompt agent vérifié : {p_name}")

    # 3. Vérification des gabarits de rapports
    for t_name in EXPECTED_TEMPLATES:
        t_path = TEMPLATES_DIR / t_name
        assert t_path.exists(), f"Gabarit manquant : {t_name}"
        content = t_path.read_text(encoding="utf-8")
        assert "Sources" in content or "Références" in content, f"Section sources manquante dans {t_name}"
        print(f"[OK] Gabarit de rapport vérifié : {t_name}")

    print("==========================================================")
    print("Succès : Tous les livrables de la Phase 2 sont validés !")


if __name__ == "__main__":
    test_phase2()
