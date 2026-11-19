"""Routes des avis 👍 / 👎 sur les rapports (Phase 9)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from api.schemas import FeedbackIn
from storage.repository import feedback_repository

router = APIRouter(tags=["avis"])


@router.post("/tasks/{task_id}/feedback", summary="Noter un rapport ou une section")
def add_feedback(task_id: str, body: FeedbackIn):
    if body.rating not in (1, -1):
        raise HTTPException(400, "rating doit valoir 1 (👍) ou -1 (👎).")
    fid = feedback_repository.add(task_id, body.rating, body.section, body.comment)
    return {"id": fid, "task_id": task_id}


@router.get("/feedback", summary="Liste des avis")
def list_feedback(task_id: Optional[str] = None):
    return feedback_repository.list(task_id=task_id)
