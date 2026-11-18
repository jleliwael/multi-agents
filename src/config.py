"""Module de gestion centralisée de la configuration de l'application.

Lit les variables définies dans le fichier .env sans aucune valeur en dur.
"""

from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

# Chemin vers la racine du projet (un niveau au-dessus de src/)
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Chargement explicite du fichier .env
ENV_FILE: Path = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)


@dataclass(frozen=True)
class Settings:
    """Structure de configuration typée pour le système multi-agents."""

    # Paramètres de l'API Ollama locale
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_planner: str = os.getenv("MODEL_PLANNER", "qwen3:14b")
    model_coder: str = os.getenv("MODEL_CODER", "qwen2.5-coder:7b")
    model_embedding: str = os.getenv("MODEL_EMBEDDING", "nomic-embed-text")

    # Chemins de stockage local
    sqlite_db_path: Path = BASE_DIR / os.getenv("SQLITE_DB_PATH", "data/history.db")
    chroma_persist_dir: Path = BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db")

    # Configuration réseau pour FastAPI et Streamlit
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    streamlit_port: int = int(os.getenv("STREAMLIT_PORT", "8501"))

    def validate(self) -> None:
        """Vérifie que les variables obligatoires sont bien renseignées."""
        if not self.ollama_base_url:
            raise ValueError("L'URL d'Ollama (OLLAMA_BASE_URL) est obligatoire.")
        if not self.model_planner:
            raise ValueError("Le modèle du planificateur (MODEL_PLANNER) est obligatoire.")
        if not self.model_coder:
            raise ValueError("Le modèle de code (MODEL_CODER) est obligatoire.")
        if not self.model_embedding:
            raise ValueError("Le modèle d'embedding (MODEL_EMBEDDING) est obligatoire.")


# Instance unique de configuration importable partout
settings = Settings()
settings.validate()
