"""Module de sécurité et d'approbation humaine (Human-in-the-Loop).

Intercepte toute action jugée sensible :
- Exécution de code Python dans data/sandbox/
- Requête réseau sortante (recherche web / téléchargement de page)

Deux modes de validation :
- Terminal (par défaut) : la question est posée dans la console (o/N).
- Interface web : l'API installe un « fournisseur » d'approbation ; la demande apparaît
  dans le navigateur et l'agent attend la réponse (refus automatique après un délai).
Sans validation activée (REQUIRE_HUMAN_APPROVAL=false), tout est autorisé.
"""

from __future__ import annotations

import contextvars
import sys
from typing import Callable, Optional

from config import settings
from logging_.journal import journal

# Tâche en cours dans ce fil d'exécution (renseignée par l'API pour rattacher les demandes)
current_task_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_task_id", default="inconnue")

# Fournisseur externe : (task_id, action, cible, détails) -> bool
ApprovalProvider = Callable[[str, str, str, Optional[str]], bool]
_provider: Optional[ApprovalProvider] = None


def set_approval_provider(provider: Optional[ApprovalProvider]) -> None:
    """Installe (ou retire avec None) le mécanisme de validation utilisé à la place du terminal."""
    global _provider
    _provider = provider


class SecurityApproval:
    """Gestionnaire d'approbation humaine pour les opérations à risque."""

    @staticmethod
    def require_approval(action: str, target: str, details: Optional[str] = None) -> bool:
        """Demande une validation humaine si la politique de sécurité est activée."""
        if not settings.require_human_approval:
            return True

        task_id = current_task_id.get()
        if _provider is not None:
            try:
                approved = bool(_provider(task_id, action, target, details))
            except Exception:
                approved = False  # en cas de doute, on refuse
        else:
            approved = SecurityApproval._ask_terminal(action, target, details)

        journal.log_event(
            task_id=task_id if task_id != "inconnue" else "security-gate",
            agent="security",
            action=action,
            duration_ms=0,
            result={"target": target, "approved": approved},
        )
        return approved

    @staticmethod
    def _ask_terminal(action: str, target: str, details: Optional[str]) -> bool:
        print("\n" + "!" * 70)
        print("                 [ALERTE SÉCURITÉ - VALIDATION REQUISE]                 ")
        print("!" * 70)
        print(f"Action sensible : {action}")
        print(f"Cible           : {target}")
        if details:
            print(f"Détails         : {details}")
        print("-" * 70)

        if sys.stdin.isatty():
            try:
                choice = input("--> Autoriser cette action ? (o/N) : ").strip().lower()
                approved = choice in ("o", "oui", "y", "yes")
            except (EOFError, KeyboardInterrupt):
                approved = False
        else:
            # En environnement non interactif (tests automatisés), refus par précaution
            print("[SÉCURITÉ] Environnement non interactif : action bloquée par défaut.")
            approved = False

        print(f"--> Décision utilisateur : {'AUTORISÉ' if approved else 'REFUSÉ'}\n" + "!" * 70 + "\n")
        return approved


# Helper global importable
require_approval = SecurityApproval.require_approval
