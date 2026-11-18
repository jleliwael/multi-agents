"""Gestionnaire de limites d'exécution par tâche.

Surveille en temps réel le nombre d'étapes, de recherches web, de pages lues,
de tokens consommés et le temps écoulé. Lève LimitExceeded dès qu'un seuil
est dépassé, ce qui déclenche la génération d'un rapport partiel marqué INCOMPLET.
"""

import time
from dataclasses import dataclass, field
from config import settings


class LimitExceeded(Exception):
    """Exception levée quand une limite de tâche est atteinte."""

    def __init__(self, reason: str, is_partial: bool = True):
        super().__init__(reason)
        self.reason = reason
        self.is_partial = is_partial


@dataclass
class TaskLimits:
    """Compteurs de ressources consommées pour une tâche en cours.

    Instancier en début de tâche, puis appeler check() avant chaque action coûteuse.
    """

    # Valeurs maximales (issues de config.py → .env)
    max_steps: int = field(default_factory=lambda: settings.max_steps)
    max_web_searches: int = field(default_factory=lambda: settings.max_web_searches)
    max_pages_read: int = field(default_factory=lambda: settings.max_pages_read)
    max_tokens: int = field(default_factory=lambda: settings.max_tokens)
    max_seconds: int = field(default_factory=lambda: settings.max_seconds)

    # Compteurs courants (incrémentés manuellement par les appelants)
    steps_done: int = 0
    web_searches_done: int = 0
    pages_read: int = 0
    tokens_used: int = 0

    # Instant de démarrage (initialisé automatiquement)
    _start_time: float = field(default_factory=time.time, repr=False)

    def elapsed_seconds(self) -> float:
        """Retourne le nombre de secondes écoulées depuis la création de l'objet."""
        return time.time() - self._start_time

    def add_tokens(self, tokens_in: int, tokens_out: int) -> None:
        """Ajoute des tokens consommés par un appel LLM."""
        self.tokens_used += tokens_in + tokens_out

    def check(self, action: str = "") -> None:
        """Vérifie toutes les limites et lève LimitExceeded si l'une est dépassée.

        Args:
            action: Description courte de l'action en cours (pour le message d'erreur).
        """
        prefix = f"[Action : {action}] " if action else ""

        if self.steps_done >= self.max_steps:
            raise LimitExceeded(
                f"{prefix}Nombre maximum d'étapes atteint ({self.steps_done}/{self.max_steps})."
            )

        if self.web_searches_done >= self.max_web_searches:
            raise LimitExceeded(
                f"{prefix}Nombre maximum de recherches web atteint "
                f"({self.web_searches_done}/{self.max_web_searches})."
            )

        if self.pages_read >= self.max_pages_read:
            raise LimitExceeded(
                f"{prefix}Nombre maximum de pages lues atteint "
                f"({self.pages_read}/{self.max_pages_read})."
            )

        if self.tokens_used >= self.max_tokens:
            raise LimitExceeded(
                f"{prefix}Quota de tokens dépassé ({self.tokens_used}/{self.max_tokens})."
            )

        elapsed = self.elapsed_seconds()
        if elapsed >= self.max_seconds:
            raise LimitExceeded(
                f"{prefix}Temps maximum dépassé ({round(elapsed, 1)}s / {self.max_seconds}s)."
            )

    def summary(self) -> dict:
        """Retourne un résumé lisible des compteurs actuels."""
        return {
            "steps": f"{self.steps_done}/{self.max_steps}",
            "web_searches": f"{self.web_searches_done}/{self.max_web_searches}",
            "pages_read": f"{self.pages_read}/{self.max_pages_read}",
            "tokens": f"{self.tokens_used}/{self.max_tokens}",
            "elapsed_s": f"{round(self.elapsed_seconds(), 1)}/{self.max_seconds}",
        }
