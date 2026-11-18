"""Script de vérification pour la Phase 3 (Choix techniques et Arborescence)."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "scripts/bench_models.py",
    "docs/stack.md",
    "requirements.txt",
    "main.py",
    "start.ps1",
    "docker-compose.yml",
    "llm/ollama_llm.py",
    "agents/base.py",
    "orchestrator/orchestrator.py",
    "tools/documents.py",
    "memory/long_term.py",
    "storage/db.py",
    "security/paths.py",
    "logging_/journal.py",
    "api/app.py",
    "ui/app.py",
    "tests/conftest.py"
]


def test_phase3() -> None:
    print("=== Contrôle de la Phase 3 : Choix Techniques et Arborescence ===")

    for rf in REQUIRED_FILES:
        p = BASE_DIR / rf
        assert p.exists(), f"Fichier requis manquant : {rf}"
        print(f"[OK] Fichier présent : {rf}")

    # Vérification des versions fixées dans requirements.txt
    req_content = (BASE_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "pymupdf==" in req_content, "pymupdf version fixée absente de requirements.txt"
    assert "trafilatura==" in req_content, "trafilatura version fixée absente de requirements.txt"
    assert "python-docx==" in req_content, "python-docx version fixée absente de requirements.txt"
    assert "openpyxl==" in req_content, "openpyxl version fixée absente de requirements.txt"
    print("[OK] requirements.txt contient les versions fixées attendues.")

    print("=================================================================")
    print("Succès : Toute l'arborescence et les choix techniques sont validés !")


if __name__ == "__main__":
    test_phase3()
