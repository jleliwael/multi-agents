"""Script de test de validation pour la Phase 1.

Vérifie la lecture correcte du fichier .env et la validité de la configuration.
"""

from src.config import settings


def main() -> None:
    """Affiche et valide la configuration chargée."""
    print("=== Test de la Phase 1 : Validation de la Configuration ===")
    print(f"URL Ollama           : {settings.ollama_base_url}")
    print(f"Modèle Cerveau/Plan  : {settings.model_planner}")
    print(f"Modèle Coder         : {settings.model_coder}")
    print(f"Modèle Embeddings    : {settings.model_embedding}")
    print(f"Chemin SQLite        : {settings.sqlite_db_path}")
    print(f"Chemin ChromaDB      : {settings.chroma_persist_dir}")
    print(f"API Host / Port      : {settings.api_host}:{settings.api_port}")
    print(f"Streamlit Port       : {settings.streamlit_port}")
    print("==========================================================")
    print("Succès : Configuration chargée avec succès sans erreur !")


if __name__ == "__main__":
    main()
