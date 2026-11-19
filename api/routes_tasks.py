"""Routes REST des tâches : lancer, suivre, lire le rapport, valider les actions risquées."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from api.schemas import ApprovalDecision, ReportOut, TaskCreated, TaskSummary
from config import settings
from storage.repository import task_repository

router = APIRouter(tags=["tâches"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".md", ".csv"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 Mo par fichier


def _manager(request: Request):
    return request.app.state.manager


def save_upload(upload: UploadFile, folder: Path) -> Path:
    """Enregistre un fichier envoyé (nom nettoyé, extension et taille vérifiées)."""
    name = Path(upload.filename or "").name.strip()
    if not name or Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Fichier refusé : {name or '(sans nom)'}. Formats acceptés : "
                                 + ", ".join(sorted(ALLOWED_EXTENSIONS)))
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"{name} dépasse 20 Mo.")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    target.write_bytes(data)
    return target


@router.post("/tasks", response_model=TaskCreated, summary="Lancer une tâche")
def create_task(
    request: Request,
    objective: str = Form(..., min_length=3, max_length=4000),
    family: Optional[str] = Form(default=None, description="synthese, veille, comparatif ou question"),
    files: List[UploadFile] = File(default=[]),
):
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    saved = [str(save_upload(f, settings.uploads_dir / task_id)) for f in files if f.filename]
    full_objective = objective.strip()
    if family and family.strip().lower() not in ("", "auto"):
        full_objective = f"[Type de tâche : {family.strip().lower()}] {full_objective}"
    _manager(request).submit(full_objective, files=saved, task_id=task_id)
    return TaskCreated(task_id=task_id, status="EN_ATTENTE")


@router.get("/tasks", response_model=List[TaskSummary], summary="Historique des tâches")
def list_tasks(request: Request, limit: int = Query(50, ge=1, le=500)):
    live = {t.task_id: t for t in _manager(request).list()}
    rows: List[TaskSummary] = []
    for t in live.values():
        res = t.result or {}
        rows.append(TaskSummary(task_id=t.task_id, objective=t.objective, status=t.status,
                                created_at=t.created_at, family=res.get("family"),
                                report_path=res.get("report_path"), duration_ms=res.get("duration_ms")))
    for rec in task_repository.list_tasks(limit=limit):
        if rec.task_id not in live:
            rows.append(TaskSummary(task_id=rec.task_id, objective=rec.objective, status=rec.status,
                                    created_at=rec.created_at, family=rec.family,
                                    report_path=rec.report_path, duration_ms=rec.duration_ms))
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return rows[:limit]


@router.get("/tasks/{task_id}", summary="Statut, étapes et progression d'une tâche")
def get_task(task_id: str, request: Request):
    mgr = _manager(request)
    state = mgr.get(task_id)
    if state:
        data = state.public()
        data["pending_approvals"] = mgr.pending_approvals(task_id)
        return data
    rec = task_repository.get_task(task_id)
    if not rec:
        raise HTTPException(404, "Tâche inconnue.")
    return {"task_id": rec.task_id, "objective": rec.objective, "status": rec.status,
            "created_at": rec.created_at, "family": rec.family, "report_path": rec.report_path,
            "duration_ms": rec.duration_ms, "events": [], "pending_approvals": [], "facts": []}


def _report_path(task_id: str, request: Request) -> Path:
    state = _manager(request).get(task_id)
    path_str = (state.result or {}).get("report_path") if state else None
    if not path_str:
        rec = task_repository.get_task(task_id)
        path_str = rec.report_path if rec else None
    if not path_str:
        raise HTTPException(404, "Rapport pas encore disponible.")
    path = Path(path_str).resolve()
    # Sécurité : on ne sert que des fichiers du dossier des rapports
    if settings.reports_dir.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, "Rapport introuvable.")
    return path


@router.get("/tasks/{task_id}/report", response_model=ReportOut, summary="Rapport Markdown")
def get_report(task_id: str, request: Request):
    path = _report_path(task_id, request)
    return ReportOut(task_id=task_id, report_path=str(path), markdown=path.read_text(encoding="utf-8"))


@router.get("/tasks/{task_id}/report/download", summary="Télécharger le rapport (.md)")
def download_report(task_id: str, request: Request):
    path = _report_path(task_id, request)
    return FileResponse(path, media_type="text/markdown", filename=path.name)


@router.get("/approvals", summary="Demandes d'approbation en attente")
def list_approvals(request: Request, task_id: Optional[str] = None):
    return _manager(request).pending_approvals(task_id)


@router.post("/tasks/{task_id}/approve", summary="Autoriser ou refuser une action risquée")
def approve(task_id: str, decision: ApprovalDecision, request: Request):
    mgr = _manager(request)
    ids = {a["approval_id"] for a in mgr.pending_approvals(task_id)}
    if decision.approval_id not in ids or not mgr.decide(decision.approval_id, decision.approve):
        raise HTTPException(404, "Demande d'approbation introuvable ou déjà traitée.")
    return {"approval_id": decision.approval_id, "approve": decision.approve}
