"""Module de gestion centralisée de la configuration de l'application.

Lit les variables définies dans le fichier .env sans aucune valeur en dur.
"""

from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

# Racine du projet
BASE_DIR: Path = Path(__file__).resolve().parent

# Chargement explicite du fichier .env
ENV_FILE: Path = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)


@dataclass(frozen=True)
class Settings:
    """Structure de configuration typée pour le système multi-agents."""

    # Racine du projet accessible directement sur l'instance
    base_dir: Path = BASE_DIR

    # Paramètres de l'API Ollama locale
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_planner: str = os.getenv("MODEL_PLANNER", "qwen3:14b")
    model_coder: str = os.getenv("MODEL_CODER", "qwen2.5-coder:7b")
    model_embedding: str = os.getenv("MODEL_EMBEDDING", "nomic-embed-text")

    # Limites d'exécution et de révision
    max_tool_calls: int = int(os.getenv("MAX_TOOL_CALLS", "5"))
    max_revisions: int = int(os.getenv("MAX_REVISIONS", "2"))

    # Limites globales par tâche (réglables dans .env)
    max_steps: int = int(os.getenv("MAX_STEPS", "10"))
    max_web_searches: int = int(os.getenv("MAX_WEB_SEARCHES", "5"))
    max_pages_read: int = int(os.getenv("MAX_PAGES_READ", "30"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "50000"))
    max_seconds: int = int(os.getenv("MAX_SECONDS", "1800"))

    # Taille du contexte Ollama en tokens (Ollama utilise 4096 par défaut : trop court pour
    # le Rédacteur qui reçoit gabarit + faits + analyses). 8192 tient dans 6 Go de VRAM.
    num_ctx: int = int(os.getenv("NUM_CTX", "8192"))
    # Longueur maximale d'une réponse : évite qu'un modèle « s'emballe » pendant des minutes
    max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))
    # Délai maximal d'une réponse d'Ollama (secondes) : qwen3:14b déborde de 6 Go de VRAM, il est lent
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "900"))
    # Mode « réflexion » de qwen3 (plus lent ; désactivé par défaut)
    ollama_think: bool = os.getenv("OLLAMA_THINK", "false").lower() in ("true", "1", "yes")

    # Étapes indépendantes exécutées en parallèle (1 = séquentiel ; 2 conseillé avec 6 Go de VRAM)
    max_parallel_steps: int = int(os.getenv("MAX_PARALLEL_STEPS", "2"))

    # Option Claude (Phase 9) : utilisé pour le planificateur et le critique si une clé est fournie
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

    # Recherche Web externe (SearXNG local ou API optionnelle)
    searxng_url: str = os.getenv("SEARXNG_URL", "http://localhost:8080")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    brave_api_key: str = os.getenv("BRAVE_API_KEY", "")

    # Sécurité et Approbation Humaine (Human-in-the-Loop)
    require_human_approval: bool = os.getenv("REQUIRE_HUMAN_APPROVAL", "false").lower() in ("true", "1", "yes")

    # Chemins de stockage local (relatifs à la racine du projet)
    sqlite_db_path: Path = BASE_DIR / os.getenv("SQLITE_DB_PATH", "data/app.db")
    chroma_persist_dir: Path = BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
    workspace_dir: Path = BASE_DIR / "data" / "workspace"
    documents_dir: Path = BASE_DIR / "data" / "documents"
    uploads_dir: Path = BASE_DIR / "data" / "uploads"
    sandbox_dir: Path = BASE_DIR / "data" / "sandbox"
    reports_dir: Path = BASE_DIR / "data" / "reports"
    eval_dir: Path = BASE_DIR / "data" / "eval"
    logs_dir: Path = BASE_DIR / "data" / "logs"

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
        if self.max_tool_calls <= 0:
            raise ValueError("MAX_TOOL_CALLS doit être strictement supérieur à 0.")
        if self.max_revisions < 0:
            raise ValueError("MAX_REVISIONS doit être supérieur ou égal à 0.")


# Instance unique de configuration importable partout
settings = Settings()
settings.validate()
