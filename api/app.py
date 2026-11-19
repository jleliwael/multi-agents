"""Application FastAPI (Phase 8).

Lancement :
    .venv\\Scripts\\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000
Documentation interactive : http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from api import routes_documents, routes_feedback, routes_tasks
from api.schemas import HealthOut
from api.task_manager import TaskManager
from config import settings
from llm.model_resolver import installed_models, resolve_model


def default_orchestrator_factory():
    from orchestrator.orchestrator import Orchestrator
    return Orchestrator()


def create_app(orchestrator_factory: Optional[Callable[[], Any]] = None) -> FastAPI:
    app = FastAPI(
        title="Système multi-agents local",
        description="Recherche, veille et analyse de documents avec une équipe d'agents IA (Ollama + Qwen).",
        version="1.0.0",
    )
    app.state.manager = TaskManager(orchestrator_factory or default_orchestrator_factory)

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/docs")

    @app.get("/health", response_model=HealthOut, tags=["système"], summary="État d'Ollama et des modèles")
    def health():
        models = installed_models(force=True)
        return HealthOut(
            ollama=bool(models),
            models=models,
            planner_model=resolve_model(settings.model_planner),
            approval_required=settings.require_human_approval,
            details={"modele_souhaite": settings.model_planner, "parallelisme": settings.max_parallel_steps},
        )

    app.include_router(routes_tasks.router)
    app.include_router(routes_documents.router)
    app.include_router(routes_feedback.router)
    return app


app = create_app()
