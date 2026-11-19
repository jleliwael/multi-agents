"""Exécution des tâches en arrière-plan pour l'API (Phase 8).

Chaque tâche tourne dans son propre fil d'exécution. Le gestionnaire garde en mémoire
le statut, le journal de progression et les demandes d'approbation en attente,
pour que l'interface puisse suivre la tâche en direct. Le résultat final est aussi
enregistré dans SQLite par l'orchestrateur (historique durable).
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from security.approval import current_task_id, set_approval_provider

# Délai maximal d'attente d'une décision humaine avant refus automatique
APPROVAL_TIMEOUT_S = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ApprovalRequest:
    approval_id: str
    task_id: str
    action: str
    target: str
    details: Optional[str]
    created_at: str = field(default_factory=_now)
    decision: Optional[bool] = None
    _event: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id, "task_id": self.task_id, "action": self.action,
            "target": self.target, "details": self.details, "created_at": self.created_at,
            "decision": self.decision,
        }


@dataclass
class TaskState:
    task_id: str
    objective: str
    files: List[str]
    status: str = "EN_ATTENTE"  # EN_ATTENTE, EN_COURS, COMPLETED, INCOMPLET, ECHEC
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None
    events: List[Dict[str, str]] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def public(self, with_result: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "task_id": self.task_id, "objective": self.objective, "files": self.files,
            "status": self.status, "created_at": self.created_at, "finished_at": self.finished_at,
            "events": list(self.events), "error": self.error,
        }
        if with_result and self.result:
            data.update({
                "family": self.result.get("family"),
                "plan": self.result.get("plan"),
                "report_path": self.result.get("report_path"),
                "duration_ms": self.result.get("duration_ms"),
                "facts": self.result.get("facts", []),
                "limit_reason": self.result.get("limit_reason"),
            })
        return data


class TaskManager:
    """Lance les tâches, suit leur progression et relaie les demandes d'approbation."""

    def __init__(self, orchestrator_factory: Callable[[], Any], max_concurrent: int = 1):
        self._orchestrator_factory = orchestrator_factory
        self._tasks: Dict[str, TaskState] = {}
        self._approvals: Dict[str, ApprovalRequest] = {}
        self._lock = threading.Lock()
        # Une seule tâche à la fois par défaut : le GPU de 6 Go ne supporte pas plus
        self._slots = threading.Semaphore(max(1, max_concurrent))
        set_approval_provider(self._ask_approval)

    # ------------------------------------------------------------------ tâches
    def submit(self, objective: str, files: Optional[List[str]] = None, task_id: Optional[str] = None) -> str:
        tid = task_id or f"task-{uuid.uuid4().hex[:8]}"
        state = TaskState(task_id=tid, objective=objective, files=list(files or []))
        with self._lock:
            self._tasks[tid] = state
        self._event(state, "Tâche reçue, en attente d'un créneau d'exécution.")
        threading.Thread(target=self._run, args=(state,), name=f"tache-{tid}", daemon=True).start()
        return tid

    def _run(self, state: TaskState) -> None:
        with self._slots:
            state.status = "EN_COURS"
            token = current_task_id.set(state.task_id)
            try:
                orchestrator = self._orchestrator_factory()
                result = orchestrator.run(
                    objective=state.objective,
                    task_id=state.task_id,
                    files=state.files,
                    on_progress=lambda msg: self._event(state, msg),
                )
                state.result = result
                state.status = result.get("status", "COMPLETED")
            except Exception as exc:
                state.status = "ECHEC"
                state.error = f"{type(exc).__name__} : {exc}"
                self._event(state, f"❌ Échec de la tâche : {state.error}")
            finally:
                current_task_id.reset(token)
                state.finished_at = _now()
                # Les demandes encore ouvertes de cette tâche sont refusées
                for req in self.pending_approvals(state.task_id):
                    self.decide(req["approval_id"], False)

    def _event(self, state: TaskState, message: str) -> None:
        with self._lock:
            state.events.append({"time": _now(), "message": message})

    def get(self, task_id: str) -> Optional[TaskState]:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self) -> List[TaskState]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)

    # ------------------------------------------------------------- approbations
    def _ask_approval(self, task_id: str, action: str, target: str, details: Optional[str]) -> bool:
        """Appelé depuis le fil de l'agent : crée la demande puis attend la décision humaine."""
        req = ApprovalRequest(approval_id=uuid.uuid4().hex[:10], task_id=task_id,
                              action=action, target=target, details=details)
        with self._lock:
            self._approvals[req.approval_id] = req
        state = self.get(task_id)
        if state:
            self._event(state, f"🔐 Validation requise : {action} → {target}")
        decided = req._event.wait(APPROVAL_TIMEOUT_S)
        approved = bool(decided and req.decision)
        if state:
            verdict = "autorisée" if approved else ("refusée" if decided else "refusée (délai dépassé)")
            self._event(state, f"Action {action} {verdict}.")
        return approved

    def pending_approvals(self, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            reqs = [r for r in self._approvals.values() if r.decision is None]
        return [r.public() for r in reqs if task_id is None or r.task_id == task_id]

    def decide(self, approval_id: str, approve: bool) -> bool:
        with self._lock:
            req = self._approvals.get(approval_id)
            if not req or req.decision is not None:
                return False
            req.decision = bool(approve)
        req._event.set()
        return True

    def wait_finished(self, task_id: str, timeout: float = 30) -> Optional[TaskState]:
        """Utilitaire pour les tests et scripts : attend la fin d'une tâche."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.get(task_id)
            if state and state.finished_at:
                return state
            time.sleep(0.05)
        return self.get(task_id)
