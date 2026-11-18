"""Module de sécurité et d'approbation humaine (Human-in-the-Loop).

Intercepte toute action jugée sensible :
- Écriture de fichier hors de data/workspace/
- Exécution de code Python dans data/sandbox/
- Requête réseau sortante (Web search / téléchargement de page)
Demande une confirmation explicite dans la console de l'utilisateur.
"""

import sys
from typing import Optional
from config import settings
from logging_.journal import journal


class SecurityApproval:
    """Gestionnaire d'approbation humaine pour les opérations à risque."""

    @staticmethod
    def require_approval(action: str, target: str, details: Optional[str] = None) -> bool:
        """Demande une validation humaine si la politique de sécurité est activée."""
        # Si l'approbation humaine n'est pas activée dans le .env, on autorise directement
        if not settings.require_human_approval:
            return True

        print("\n" + "!" * 70)
        print("                 [ALERTE SÉCURITÉ - VALIDATION REQUISE]                 ")
        print("!" * 70)
        print(f"Action sensible : {action}")
        print(f"Cible           : {target}")
        if details:
            print(f"Détails         : {details}")
        print("-" * 70)

        # Si l'environnement est interactif
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

        status_str = "AUTORISÉ" if approved else "REFUSÉ"
        print(f"--> Décision utilisateur : {status_str}\n" + "!" * 70 + "\n")

        journal.log_event(
            task_id="security-gate",
            agent="security",
            action=action,
            duration_ms=0,
            result={"target": target, "approved": approved}
        )

        return approved


# Helper global importable
require_approval = SecurityApproval.require_approval
