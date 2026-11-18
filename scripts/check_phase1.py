"""Script de vérification pour la Phase 1 (Définition du besoin).

Vérifie l'existence et la validité du cahier des charges et des 10 tâches de référence.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"


def test_docs() -> None:
    cahier_charges = DOCS_DIR / "cahier_des_charges.md"
    taches_json = DOCS_DIR / "taches_reference.json"

    assert cahier_charges.exists(), "Erreur : docs/cahier_des_charges.md introuvable"
    assert taches_json.exists(), "Erreur : docs/taches_reference.json introuvable"

    with open(taches_json, "r", encoding="utf-8") as f:
        taches = json.load(f)

    assert isinstance(taches, list), "Le fichier JSON doit contenir une liste de tâches"
    assert len(taches) == 10, f"Attendu 10 tâches, trouvé {len(taches)}"

    for i, t in enumerate(taches, 1):
        assert "id" in t and t["id"] == f"task-{i:02d}", f"ID invalide pour la tâche {i}"
        assert "titre" in t and t["titre"], f"Titre manquant pour la tâche {i}"
        assert "entree" in t, f"Entrée manquante pour la tâche {i}"
        assert "sortie_attendue" in t, f"Sortie attendue manquante pour la tâche {i}"
        assert "criteres" in t, f"Critères manquants pour la tâche {i}"
        assert "temps_max_secondes" in t["criteres"], f"Temps max manquant pour la tâche {i}"
        assert t["criteres"]["cout"] == "0.00 EUR", f"Le coût doit être 0.00 EUR pour la tâche {i}"

    print("=== Validation Phase 1 Réussie ===")
    print(f"[OK] Cahier des charges : {cahier_charges.name} ({cahier_charges.stat().st_size} octets)")
    print(f"[OK] Tâches de référence : {len(taches)} tâches validées avec succès.")
    for t in taches:
        print(f"  - [{t['id']}] {t['titre']} ({t['difficulte']}, max {t['criteres']['temps_max_secondes']}s)")


if __name__ == "__main__":
    test_docs()
