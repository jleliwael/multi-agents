"""Tests de l'API FastAPI (Phase 8) avec un orchestrateur simulé : aucun appel à Ollama."""

import time
import types
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import security.approval as approval
from api.app import create_app
from config import settings


class FakeOrchestrator:
    """Écrit un vrai rapport dans data/reports/ ; demande une approbation si l'objectif contient « web »."""

    def run(self, objective, task_id=None, files=None, on_progress=None):
        on_progress("Étape 1/2 : Exécution par l'agent 'READER'...")
        if "web" in objective:
            allowed = approval.require_approval("web_search", "ollama nouveautés")
            on_progress(f"recherche web {'faite' if allowed else 'annulée'}")
        if "plante" in objective:
            raise RuntimeError("panne simulée")
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        path = settings.reports_dir / f"test_api_{task_id}.md"
        path.write_text(f"# Rapport\n\nObjectif : {objective}\nFichiers : {len(files or [])}\n", encoding="utf-8")
        return {"task_id": task_id, "status": "COMPLETED", "family": "synthese", "plan": {"steps": []},
                "report_path": str(path), "final_output": path.read_text(encoding="utf-8"),
                "facts": [], "duration_ms": 12.0}


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.app = create_app(orchestrator_factory=FakeOrchestrator)
        self.client = TestClient(self.app)
        self.manager = self.app.state.manager

    def tearDown(self):
        approval.set_approval_provider(None)
        for p in settings.reports_dir.glob("test_api_*.md"):
            p.unlink()

    def _wait(self, task_id):
        state = self.manager.wait_finished(task_id, timeout=10)
        self.assertIsNotNone(state.finished_at, "la tâche aurait dû se terminer")
        return state

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertIn("planner_model", r.json())

    def test_task_lifecycle_with_upload(self):
        r = self.client.post("/tasks", data={"objective": "Résume ce document"},
                             files=[("files", ("note.txt", b"Le CA est de 45 M EUR.", "text/plain"))])
        self.assertEqual(r.status_code, 200, r.text)
        tid = r.json()["task_id"]
        self._wait(tid)

        detail = self.client.get(f"/tasks/{tid}").json()
        self.assertEqual(detail["status"], "COMPLETED")
        self.assertTrue(any("READER" in e["message"] for e in detail["events"]))
        self.assertTrue(detail["files"][0].endswith("note.txt"))

        report = self.client.get(f"/tasks/{tid}/report").json()
        self.assertIn("Fichiers : 1", report["markdown"])
        self.assertEqual(self.client.get(f"/tasks/{tid}/report/download").status_code, 200)
        self.assertIn(tid, [t["task_id"] for t in self.client.get("/tasks").json()])

    def test_rejects_dangerous_upload(self):
        r = self.client.post("/tasks", data={"objective": "test"},
                             files=[("files", ("virus.exe", b"MZ", "application/octet-stream"))])
        self.assertEqual(r.status_code, 400)

    def test_unknown_task_returns_404(self):
        self.assertEqual(self.client.get("/tasks/inexistante").status_code, 404)
        self.assertEqual(self.client.get("/tasks/inexistante/report").status_code, 404)

    def test_failure_is_reported(self):
        tid = self.client.post("/tasks", data={"objective": "ceci plante"}).json()["task_id"]
        state = self._wait(tid)
        self.assertEqual(state.status, "ECHEC")
        self.assertIn("panne simulée", self.client.get(f"/tasks/{tid}").json()["error"])

    def test_human_approval_from_browser(self):
        with mock.patch.object(approval, "settings", types.SimpleNamespace(require_human_approval=True)):
            tid = self.client.post("/tasks", data={"objective": "veille web"}).json()["task_id"]
            pending = []
            for _ in range(100):
                pending = self.client.get("/approvals", params={"task_id": tid}).json()
                if pending:
                    break
                time.sleep(0.05)
            self.assertEqual(len(pending), 1, "une demande d'approbation doit apparaître")
            r = self.client.post(f"/tasks/{tid}/approve",
                                 json={"approval_id": pending[0]["approval_id"], "approve": True})
            self.assertEqual(r.status_code, 200)
            self._wait(tid)
        events = [e["message"] for e in self.client.get(f"/tasks/{tid}").json()["events"]]
        self.assertIn("recherche web faite", events)

    def test_feedback(self):
        import tempfile
        from pathlib import Path
        import api.routes_feedback as rf
        from storage.repository import FeedbackRepository
        temp_repo = FeedbackRepository(db_path=Path(tempfile.mkdtemp()) / "fb.db")
        patcher = mock.patch.object(rf, "feedback_repository", temp_repo)
        patcher.start()
        self.addCleanup(patcher.stop)
        r = self.client.post("/tasks/task-x/feedback", json={"rating": -1, "section": "Résumé", "comment": "trop court"})
        self.assertEqual(r.status_code, 200)
        items = self.client.get("/feedback", params={"task_id": "task-x"}).json()
        self.assertTrue(any(i["comment"] == "trop court" and i["rating"] == -1 for i in items))
        self.assertEqual(self.client.post("/tasks/task-x/feedback", json={"rating": 5}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
