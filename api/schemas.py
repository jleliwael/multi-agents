"""Schémas Pydantic des requêtes et réponses HTTP de l'API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskCreated(BaseModel):
    task_id: str
    status: str


class ApprovalDecision(BaseModel):
    approval_id: str = Field(..., description="Identifiant de la demande (voir GET /approvals)")
    approve: bool = Field(..., description="true = autoriser, false = refuser")


class FeedbackIn(BaseModel):
    rating: int = Field(..., description="1 = 👍, -1 = 👎")
    section: str = Field(default="rapport", max_length=200)
    comment: str = Field(default="", max_length=2000)


class ReportOut(BaseModel):
    task_id: str
    report_path: str
    markdown: str


class DocumentInfo(BaseModel):
    name: str
    size_kb: float
    indexed: bool


class HealthOut(BaseModel):
    ollama: bool
    models: List[str]
    planner_model: str
    approval_required: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class TaskSummary(BaseModel):
    task_id: str
    objective: str
    status: str
    created_at: str
    family: Optional[str] = None
    report_path: Optional[str] = None
    duration_ms: Optional[float] = None
