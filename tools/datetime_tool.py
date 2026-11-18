"""Outil fournissant l'horodatage, la date courante et les calculs temporels."""

from datetime import datetime, timedelta, timezone
from tools.registry import tool


@tool(name="get_current_datetime", description="Retourne la date et l'heure actuelles (format ISO et lisible).")
def get_current_datetime() -> str:
    """Fournit l'heure et la date courantes."""
    now = datetime.now()
    return f"Date et heure actuelles : {now.strftime('%d/%m/%Y %H:%M:%S')} (ISO: {now.isoformat()})"


@tool(name="calculate_date_delta", description="Calcule une date future ou passée en ajoutant/retranchant un nombre de jours.")
def calculate_date_delta(days: int) -> str:
    """Calcule une date décalée de N jours."""
    target_date = datetime.now() + timedelta(days=days)
    direction = "futur" if days >= 0 else "passé"
    return f"Date calculée ({days} jours dans le {direction}) : {target_date.strftime('%d/%m/%Y')}"
