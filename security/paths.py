"""Validation stricte des chemins de fichiers pour interdire toute écriture hors de data/workspace/ et data/sandbox/.

Bloque explicitement :
- Les séquences de traversée de répertoire (../ et ..\\ )
- Les chemins absolus pointant hors des zones autorisées
- Toute lecture de fichiers système ou de configuration sensibles

Les documents originaux (data/documents/, data/uploads/) sont en lecture seule.
"""

from pathlib import Path
from typing import List
from config import settings


class SecurityError(PermissionError):
    """Exception levée en cas de tentative d'accès à un chemin non autorisé."""
    pass


# Répertoires autorisés en lecture (documents originaux → lecture seule)
ALLOWED_READ_DIRS: List[Path] = [
    settings.documents_dir.resolve(),
    settings.uploads_dir.resolve(),
    settings.workspace_dir.resolve(),
    settings.sandbox_dir.resolve(),
    settings.reports_dir.resolve(),
    settings.eval_dir.resolve(),
    settings.logs_dir.resolve(),
    (settings.base_dir / "tests" / "fixtures").resolve(),
]

# Répertoires autorisés en écriture (workspace et sandbox uniquement)
ALLOWED_WRITE_DIRS: List[Path] = [
    settings.workspace_dir.resolve(),
    settings.sandbox_dir.resolve(),
    settings.reports_dir.resolve(),
    settings.eval_dir.resolve(),
    settings.logs_dir.resolve(),
]

# Répertoires en lecture seule (écriture interdite même si dans ALLOWED_READ_DIRS)
READ_ONLY_DIRS: List[Path] = [
    settings.documents_dir.resolve(),
    settings.uploads_dir.resolve(),
]


def _contains_traversal(raw_path: str) -> bool:
    """Détecte les séquences de traversée de répertoire dans la chaîne brute."""
    # Bloque ../  ..\  %2e%2e et variantes URL-encodées
    dangerous = ["../", "..\\", "%2e%2e", "...."]
    path_lower = raw_path.lower().replace("\\\\", "\\")
    return any(seq in path_lower for seq in dangerous)


def validate_path(path: str | Path, mode: str = "read") -> Path:
    """Valide un chemin et retourne sa version résolue si l'accès est autorisé.

    Args:
        path: Chemin à valider (relatif ou absolu).
        mode: "read" ou "write".

    Returns:
        Le chemin résolu (Path) si l'accès est autorisé.

    Raises:
        SecurityError: Si le chemin est dangereux ou hors des zones autorisées.
    """
    raw = str(path)

    # 1. Blocage des séquences de traversée dans la chaîne brute
    if _contains_traversal(raw):
        raise SecurityError(
            f"Chemin refusé : séquence de traversée de répertoire détectée dans '{raw}'."
        )

    # 2. Résolution du chemin
    try:
        resolved = Path(raw).resolve()
    except Exception as e:
        raise SecurityError(f"Chemin invalide ou impossible à résoudre : '{raw}'. Erreur : {e}")

    # 3. Vérification selon le mode
    if mode == "write":
        allowed = ALLOWED_WRITE_DIRS
        # Écriture dans un dossier en lecture seule → interdit
        for ro_dir in READ_ONLY_DIRS:
            try:
                resolved.relative_to(ro_dir)
                raise SecurityError(
                    f"Écriture interdite : '{resolved}' est dans un répertoire en lecture seule ({ro_dir.name}/)."
                )
            except ValueError:
                pass
    else:
        allowed = ALLOWED_READ_DIRS

    for allowed_dir in allowed:
        try:
            resolved.relative_to(allowed_dir)
            return resolved  # ✅ Chemin dans une zone autorisée
        except ValueError:
            continue

    zones = ", ".join(str(d) for d in allowed)
    raise SecurityError(
        f"Accès refusé en mode '{mode}' : '{resolved}' est hors des zones autorisées.\n"
        f"Zones valides : {zones}"
    )


def ensure_read_only(path: Path) -> None:
    """Vérifie qu'un chemin pointe vers un fichier dans un dossier en lecture seule.

    Lève SecurityError si le fichier se trouve dans une zone où l'écriture est autorisée.
    Cette fonction est utilisée pour s'assurer que les documents originaux ne sont pas modifiés.
    """
    resolved = path.resolve()
    for ro_dir in READ_ONLY_DIRS:
        try:
            resolved.relative_to(ro_dir)
            return  # ✅ Bien dans une zone en lecture seule
        except ValueError:
            pass
    # Si le fichier n'est pas dans un dossier read-only, on vérifie qu'il n'est pas dans un dossier write
    for w_dir in ALLOWED_WRITE_DIRS:
        try:
            resolved.relative_to(w_dir)
            raise SecurityError(
                f"Incohérence : le fichier '{resolved.name}' devrait être en lecture seule "
                f"mais se trouve dans un répertoire d'écriture ({w_dir.name}/)."
            )
        except ValueError:
            pass
