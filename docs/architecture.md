# Spécification de l'Architecture Multi-Agents

Ce document détaille l'architecture logicielle, les contrats d'échange de données (modèles Pydantic) et la structure du journal d'audit JSONL.

---

## 1. Schéma d'Architecture Global

```mermaid
flowchart TD
    subgraph UI ["Interface Utilisateur"]
        STREAMLIT["Streamlit UI (Port 8501)"]
    end

    subgraph BACKEND ["Backend API (Port 8000)"]
        FASTAPI["FastAPI App (app.py)"]
        TASK_ROUTER["Routes Tâches & Validation"]
    end

    subgraph ORCHESTRATION ["Cœur d'Orchestration"]
        ORCHESTRATOR["Orchestrateur Principal"]
        SHORT_TERM["Mémoire Court Terme (RAM)"]
        SECURITY["Garde-fous Sécurité & Approbation"]
    end

    subgraph AGENTS ["Équipe d'Agents Spécialistes"]
        PLANNER["Planificateur (qwen3:14b)"]
        RESEARCHER["Chercheur Web (qwen3:14b)"]
        READER["Lecteur Documents (qwen3:14b)"]
        ANALYST["Analyste (qwen3:14b)"]
        CODER["Codeur Python (qwen2.5-coder:7b)"]
        WRITER["Rédacteur (qwen3:14b)"]
        CRITIC["Critique Qualité (qwen3:14b)"]
    end

    subgraph TOOLS ["Boîte à Outils (Tools)"]
        WEB_TOOL["web_search"]
        DOC_TOOL["documents & parser"]
        CODE_RUNNER["code_runner (Sandbox data/sandbox/)"]
        CALC_TOOL["calculator"]
    end

    subgraph STORAGE ["Stockage & Mémoire Long Terme"]
        SQLITE[("SQLite (data/app.db)")]
        CHROMA[("ChromaDB Vectorielle (data/chroma/)")]
        JSONL_LOG[("Journal JSONL (data/logs/)")]
    end

    %% Flux d'interaction
    STREAMLIT <-->|Requêtes REST & SSE| FASTAPI
    FASTAPI --> TASK_ROUTER
    TASK_ROUTER --> ORCHESTRATOR

    ORCHESTRATOR <--> SHORT_TERM
    ORCHESTRATOR --> SECURITY
    SECURITY -.->|Validation requise| STREAMLIT

    ORCHESTRATOR --> PLANNER
    PLANNER -.->|TaskPlan JSON| ORCHESTRATOR

    ORCHESTRATOR --> READER & RESEARCHER & ANALYST & CODER & WRITER
    READER --> DOC_TOOL & CHROMA
    RESEARCHER --> WEB_TOOL
    CODER --> CODE_RUNNER

    WRITER --> CRITIC
    CRITIC -.->|is_approved = false (max 2 révisions)| WRITER
    CRITIC -.->|is_approved = true| ORCHESTRATOR

    ORCHESTRATOR --> SQLITE
    ORCHESTRATOR --> JSONL_LOG
```

---

## 2. Contrats d'Échange de Données (Modèles Pydantic)

Tous les échanges de données entre agents et composants sont strictement typés. Voici les définitions canoniques :

```python
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    DOCUMENT = "document"
    WEB = "web"


class ConfidenceLevel(str, Enum):
    HIGH = "haute"
    MEDIUM = "moyenne"
    LOW = "faible"


class Fact(BaseModel):
    """Unité atomique d'information certifiée et traçable."""
    assertion: str = Field(..., description="Énoncé synthétique du fait extrait")
    source_type: SourceType = Field(..., description="Type de source : document local ou web")
    source_name: str = Field(..., description="Nom du fichier local ou URL de la page web")
    page_or_section: str = Field(..., description="Numéro de page ou nom de section")
    exact_quote: str = Field(..., description="Citation exacte copiée mot pour mot de la source")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.HIGH, description="Niveau de confiance évalué")


class PlanStep(BaseModel):
    """Étape individuelle planifiée par le Planificateur."""
    step_id: int
    agent: str = Field(..., description="Nom de l'agent assigné : reader, researcher, analyst, coder, writer")
    action: str = Field(..., description="Description concise de la consigne d'exécution")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Paramètres d'entrée de l'étape")
    depends_on: List[int] = Field(default_factory=list, description="IDs des étapes préalables requises")


class TaskPlan(BaseModel):
    """Graphe d'exécution généré par le Planificateur."""
    task_id: str
    objective: str
    steps: List[PlanStep]


class StepResult(BaseModel):
    """Résultat produit par un agent à la fin d'une étape."""
    step_id: int
    agent: str
    success: bool
    output_text: str
    facts: List[Fact] = Field(default_factory=list)
    artifacts: List[str] = Field(default_factory=list, description="Chemins des fichiers créés")
    error: Optional[str] = None


class CriticEvaluation(BaseModel):
    """Évaluation d'assurance qualité produite par le Critique."""
    is_approved: bool = Field(..., description="True si le rapport respecte 100% des critères et des sources")
    score_qualite: float = Field(..., ge=0.0, le=10.0, description="Note globale de qualité sur 10")
    anomalies: List[str] = Field(default_factory=list, description="Écarts ou affirmations non sourcées")
    recommandations: List[str] = Field(default_factory=list, description="Consignes pour la passe de révision")


class AgentMessage(BaseModel):
    """Message structuré échangé au sein du bus de communication."""
    sender: str
    recipient: str
    task_id: str
    action: str
    payload: Dict[str, Any]
    timestamp: str
```

---

## 3. Format du Journal d'Événements JSONL

Chaque appel, transition d'état, action d'outil ou inférence LLM génère **une ligne JSON autonome** dans `data/logs/journal.jsonl`.

### Spécification des Champs
- `timestamp` : Horodatage ISO 8601 précis (ex. `"2026-11-18T23:10:05.123456"`).
- `task_id` : Identifiant unique de la tâche globale.
- `agent` : Nom de l'agent actif (`"planner"`, `"reader"`, `"researcher"`, `"analyst"`, `"coder"`, `"writer"`, `"critic"`, `"orchestrator"`).
- `action` : Nom de l'opération effectuée (`"generate_plan"`, `"extract_facts"`, `"run_sandbox_code"`, `"write_report"`, `"review"`).
- `duration_ms` : Durée d'exécution de l'opération en millisecondes.
- `tokens` : Consommation de tokens (détail `prompt_tokens`, `completion_tokens`, `total_tokens`).
- `result` : Résumé structuré ou statut du résultat.
- `error` : Message d'erreur détaillé ou `null` en cas de succès.

### Exemple Réel de Ligne JSONL
```json
{"timestamp": "2026-11-18T23:10:05.120", "task_id": "task-01", "agent": "reader", "action": "extract_facts", "duration_ms": 3450, "tokens": {"prompt_tokens": 820, "completion_tokens": 185, "total_tokens": 1005}, "result": {"facts_count": 4, "pages_read": [1, 2, 3]}, "error": null}
```
