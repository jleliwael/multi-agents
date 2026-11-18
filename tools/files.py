"""Outil de gestion sécurisée des fichiers locaux.

Applique des règles strictes de confinement de chemin :
- Écriture autorisée UNIQUEMENT dans data/workspace/
- Lecture autorisée UNIQUEMENT dans data/documents/, data/uploads/ et data/workspace/
"""

from pathlib import Path
from typing import List
from config import settings
from tools.registry import tool

# Chemins absolus canoniques autorisés
DIR_WORKSPACE = settings.workspace_dir.resolve()
DIR_DOCUMENTS = settings.documents_dir.resolve()
DIR_UPLOADS = settings.uploads_dir.resolve()

READ_ALLOWED_DIRS: List[Path] = [DIR_WORKSPACE, DIR_DOCUMENTS, DIR_UPLOADS]
WRITE_ALLOWED_DIRS: List[Path] = [DIR_WORKSPACE]


def _is_subpath(target: Path, parent: Path) -> bool:
    """Vérifie si un chemin cible est strictement contenu dans un dossier parent."""
    try:
        target.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _check_read_permission(path: Path) -> bool:
    resolved = path.resolve()
    return any(_is_subpath(resolved, d) for d in READ_ALLOWED_DIRS)


def _check_write_permission(path: Path) -> bool:
    resolved = path.resolve()
    return any(_is_subpath(resolved, d) for d in WRITE_ALLOWED_DIRS)


@tool(name="read_file", description="Lit le contenu textuel d'un fichier dans data/documents, data/uploads ou data/workspace.")
def read_file(filepath: str) -> str:
    """Lit le contenu d'un fichier si le chemin est dans les zones de lecture autorisées."""
    p = Path(filepath)
    if not p.is_absolute():
        # Recherche prioritaire dans documents, uploads, puis workspace
        candidates = [DIR_DOCUMENTS / p, DIR_UPLOADS / p, DIR_WORKSPACE / p]
        for c in candidates:
            if c.exists():
                p = c
                break
        if not p.is_absolute():
            p = DIR_DOCUMENTS / p

    if not _check_read_permission(p):
        return f"Erreur de sécurité : Lecture interdite hors des répertoires autorisés ({p})."

    if not p.exists():
        return f"Erreur : Le fichier '{p.name}' est introuvable."

    if not p.is_file():
        return f"Erreur : '{p.name}' n'est pas un fichier."

    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return p.read_text(encoding="latin-1")
        except Exception as e:
            return f"Erreur lors de la lecture du fichier : {str(e)}"


@tool(name="write_file", description="Écrit du contenu dans un fichier UNIQUEMENT dans le répertoire data/workspace.")
def write_file(filename: str, content: str) -> str:
    """Écrit du contenu dans un fichier confiné dans data/workspace/."""
    p = Path(filename)
    if not p.is_absolute():
        p = DIR_WORKSPACE / p

    if not _check_write_permission(p):
        return "Erreur de sécurité : L'écriture est strictement interdite en dehors de data/workspace/."

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Succès : Fichier écrit avec succès dans '{p.name}' ({len(content)} caractères)."
    except Exception as e:
        return f"Erreur lors de l'écriture du fichier : {str(e)}"


@tool(name="list_files", description="Liste les fichiers disponibles dans data/documents, data/uploads ou data/workspace.")
def list_files(folder_type: str = "documents") -> str:
    """Liste les fichiers d'un dossier ('documents', 'uploads' ou 'workspace')."""
    mapping = {
        "documents": DIR_DOCUMENTS,
        "uploads": DIR_UPLOADS,
        "workspace": DIR_WORKSPACE,
    }
    target_dir = mapping.get(folder_type.lower().strip())
    if not target_dir:
        return f"Erreur : Type de dossier inconnu '{folder_type}'. Choisir parmi : 'documents', 'uploads', 'workspace'."

    target_dir.mkdir(parents=True, exist_ok=True)
    files = [f.name for f in target_dir.iterdir() if f.is_file()]
    if not files:
        return f"Le dossier '{folder_type}' est actuellement vide."
    return f"Fichiers dans '{folder_type}' :\n" + "\n".join(f"- {f}" for f in files)
