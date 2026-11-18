"""Modèles de données Pydantic pour la planification et l'orchestration.

Définit Fact, Step, Plan et StepResult avec validation stricte des types.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    DOCUMENT = "document"
    WEB = "web"


class ConfidenceLevel(str, Enum):
    HIGH = "haute"
    MEDIUM = "moyenne"
    LOW = "faible"


class Fact(BaseModel):
    """Fait atomique certifié avec source vérifiable."""
    assertion: str = Field(..., description="Énoncé clair du fait extrait")
    source_type: SourceType = Field(default=SourceType.DOCUMENT, description="Type de source (document ou web)")
    source_name: str = Field(..., description="Nom du fichier source ou URL")
    page_or_section: str = Field(default="", description="Numéro de page ou section")
    exact_quote: str = Field(default="", description="Citation textuelle brute de la source")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH, description="Niveau de confiance évalué")


class Step(BaseModel):
    """Étape individuelle au sein d'un plan d'action."""
    id: int = Field(..., description="Identifiant numérique unique de l'étape (1, 2, 3...)")
    agent: str = Field(..., description="Nom de l'agent spécialiste assigné (reader, researcher, analyst, coder, writer)")
    instruction: str = Field(..., description="Consigne d'action précise pour l'agent")
    depends_on: List[int] = Field(default_factory=list, description="IDs des étapes préalables requises")


class Plan(BaseModel):
    """Plan complet d'exécution structuré en graphe d'étapes."""
    task_id: str = Field(..., description="Identifiant unique de la tâche")
    objective: str = Field(..., description="Objectif global de la mission")
    task_type: Optional[str] = Field(default="synthese", description="Famille de tâche (synthese, veille, comparatif)")
    steps: List[Step] = Field(..., min_length=1, description="Liste ordonnée des étapes")


class StepResult(BaseModel):
    """Résultat produit à l'issue de l'exécution d'une étape."""
    step_id: int
    agent: str
    success: bool = True
    output_text: str = ""
    facts: List[Fact] = Field(default_factory=list)
    artifacts: List[str] = Field(default_factory=list, description="Chemins des fichiers générés")
    error: Optional[str] = None
