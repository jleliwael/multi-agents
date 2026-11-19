"""Interface web Streamlit (Phase 8) : objectif → suivi en direct → rapport.

Lancement (l'API doit tourner) :
    .venv\\Scripts\\python.exe -m streamlit run ui/app.py
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import httpx
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from ui.export import markdown_to_docx  # noqa: E402

API = f"http://{settings.api_host}:{settings.api_port}"
STATUS_LABELS = {
    "EN_ATTENTE": "⏳ En attente", "EN_COURS": "⚙️ En cours", "COMPLETED": "✅ Terminée",
    "INCOMPLET": "⚠️ Incomplète (limite atteinte)", "ECHEC": "❌ Échec",
}
TYPES = {"Automatique": "auto", "Synthèse de documents": "synthese", "Veille web": "veille",
         "Comparatif": "comparatif", "Question sur mes documents": "question"}

st.set_page_config(page_title="Assistant multi-agents", page_icon="🤖", layout="wide")


# ----------------------------------------------------------------------------- API
def api(method: str, path: str, **kwargs):
    try:
        r = httpx.request(method, f"{API}{path}", timeout=30, **kwargs)
    except httpx.HTTPError:
        st.error(f"L'API ne répond pas à {API}. Lance d'abord `start.ps1` (ou uvicorn).")
        st.stop()
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text
        st.error(f"Erreur {r.status_code} : {detail}")
        return None
    return r.json() if "application/json" in r.headers.get("content-type", "") else r.content


def split_sections(markdown: str):
    """Découpe le rapport en sections « ## Titre » pour les avis par section."""
    parts = re.split(r"(?m)^##\s+", markdown)
    head, sections = parts[0], []
    for part in parts[1:]:
        title, _, body = part.partition("\n")
        sections.append((title.strip(), body))
    return head, sections


# ------------------------------------------------------------------------- Barre latérale
with st.sidebar:
    st.title("🤖 Assistant multi-agents")
    st.caption("Recherche, veille et analyse de documents — 100 % local")
    page = st.radio("Navigation", ["Nouvelle tâche", "Suivi", "Historique", "Bibliothèque", "Avis"],
                    index=["Nouvelle tâche", "Suivi", "Historique", "Bibliothèque", "Avis"].index(
                        st.session_state.get("page", "Nouvelle tâche")))
    st.session_state["page"] = page
    health = api("GET", "/health")
    if health:
        if health["ollama"]:
            st.success(f"Ollama actif — modèle : {health['planner_model']}")
            if health["planner_model"] != health["details"].get("modele_souhaite"):
                st.warning(f"{health['details'].get('modele_souhaite')} n'est pas installé : "
                           f"bascule sur {health['planner_model']}.")
        else:
            st.error("Ollama ne répond pas. Lance l'application Ollama.")
        st.caption("Validation humaine : " + ("activée" if health["approval_required"] else "désactivée"))


# ------------------------------------------------------------------------- Nouvelle tâche
if page == "Nouvelle tâche":
    st.header("Nouvelle tâche")
    with st.form("nouvelle_tache"):
        kind = st.selectbox("Type de tâche", list(TYPES))
        objective = st.text_area(
            "Objectif", height=120,
            placeholder="Ex. : Fais une synthèse de ces documents avec les points clés et les sources.")
        files = st.file_uploader("Fichiers (PDF, Word, Excel, texte)", accept_multiple_files=True,
                                 type=["pdf", "docx", "xlsx", "txt", "md", "csv"])
        submitted = st.form_submit_button("Lancer", type="primary")
    if submitted:
        if len(objective.strip()) < 3:
            st.warning("Écris un objectif.")
        else:
            payload = [("files", (f.name, f.getvalue(), f.type or "application/octet-stream")) for f in files or []]
            res = api("POST", "/tasks", data={"objective": objective, "family": TYPES[kind]}, files=payload or None)
            if res:
                st.session_state["task_id"] = res["task_id"]
                st.session_state["page"] = "Suivi"
                st.rerun()


# --------------------------------------------------------------------------------- Suivi
elif page == "Suivi":
    st.header("Suivi de la tâche")
    tasks = api("GET", "/tasks") or []
    if not tasks:
        st.info("Aucune tâche pour l'instant.")
        st.stop()
    ids = [t["task_id"] for t in tasks]
    current = st.session_state.get("task_id", ids[0])
    labels = {t["task_id"]: f"{t['task_id']} — {t['objective'][:60]}" for t in tasks}
    task_id = st.selectbox("Tâche", ids, index=ids.index(current) if current in ids else 0,
                           format_func=lambda i: labels[i])
    st.session_state["task_id"] = task_id
    task = api("GET", f"/tasks/{task_id}")
    if not task:
        st.stop()

    running = task["status"] in ("EN_ATTENTE", "EN_COURS")
    c1, c2, c3 = st.columns(3)
    c1.metric("Statut", STATUS_LABELS.get(task["status"], task["status"]))
    c2.metric("Type", task.get("family") or "—")
    c3.metric("Durée", f"{round((task.get('duration_ms') or 0) / 1000, 1)} s" if not running else "…")
    st.caption(f"Objectif : {task['objective']}")

    # Validations humaines en attente
    for req in task.get("pending_approvals", []):
        with st.container(border=True):
            st.warning(f"🔐 **Validation requise** — {req['action']} → `{req['target']}`")
            if req.get("details"):
                st.code(req["details"])
            a, b = st.columns(2)
            if a.button("Autoriser", key=f"ok-{req['approval_id']}", type="primary"):
                api("POST", f"/tasks/{task_id}/approve", json={"approval_id": req["approval_id"], "approve": True})
                st.rerun()
            if b.button("Refuser", key=f"no-{req['approval_id']}"):
                api("POST", f"/tasks/{task_id}/approve", json={"approval_id": req["approval_id"], "approve": False})
                st.rerun()

    with st.expander("Étapes en direct", expanded=running):
        for e in task.get("events", []):
            st.write(f"`{e['time'][11:19]}` {e['message']}")
        if task.get("plan"):
            st.markdown("**Plan :**")
            for s in task["plan"].get("steps", []):
                deps = f" (après {', '.join(map(str, s['depends_on']))})" if s.get("depends_on") else ""
                st.write(f"{s['id']}. **{s['agent']}** — {s['instruction']}{deps}")

    if task.get("facts"):
        with st.expander(f"Sources consultées ({len(task['facts'])})"):
            for i, f in enumerate(task["facts"], 1):
                st.write(f"[{i}] {f['assertion']} — *{f['source_name']} {f.get('page_or_section', '')}*")

    if task.get("error"):
        st.error(task["error"])

    if not running and task["status"] != "ECHEC":
        report = api("GET", f"/tasks/{task_id}/report")
        if report:
            st.subheader("Rapport")
            st.markdown(report["markdown"])
            d1, d2 = st.columns(2)
            d1.download_button("Télécharger (.md)", report["markdown"].encode("utf-8"),
                               file_name=f"{task_id}.md", mime="text/markdown")
            d2.download_button("Télécharger (Word)", markdown_to_docx(report["markdown"], task["objective"]),
                               file_name=f"{task_id}.docx",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

            st.subheader("Ton avis")
            _, sections = split_sections(report["markdown"])
            targets = ["Rapport entier"] + [t for t, _ in sections if not t.lower().startswith("sources")]
            with st.form(f"avis-{task_id}"):
                section = st.selectbox("Sur", targets)
                comment = st.text_input("Commentaire (facultatif)")
                g, b = st.columns(2)
                like = g.form_submit_button("👍 Utile")
                dislike = b.form_submit_button("👎 À améliorer")
            if like or dislike:
                res = api("POST", f"/tasks/{task_id}/feedback",
                          json={"rating": 1 if like else -1, "comment": comment,
                                "section": "rapport" if section == "Rapport entier" else section})
                if res:
                    st.success("Merci, ton avis est enregistré.")

    if running and st.toggle("Actualisation automatique", value=True):
        time.sleep(2)
        st.rerun()


# ----------------------------------------------------------------------------- Historique
elif page == "Historique":
    st.header("Historique")
    tasks = api("GET", "/tasks", params={"limit": 200}) or []
    if not tasks:
        st.info("Aucune tâche enregistrée.")
    for t in tasks:
        cols = st.columns([2, 5, 2, 1])
        cols[0].write(t["created_at"][:16].replace("T", " "))
        cols[1].write(t["objective"][:90])
        cols[2].write(STATUS_LABELS.get(t["status"], t["status"]))
        if cols[3].button("Ouvrir", key=f"open-{t['task_id']}"):
            st.session_state["task_id"] = t["task_id"]
            st.session_state["page"] = "Suivi"
            st.rerun()


# --------------------------------------------------------------------------- Bibliothèque
elif page == "Bibliothèque":
    st.header("Bibliothèque de documents")
    st.caption("Les documents indexés servent de mémoire long terme : les agents peuvent les retrouver "
               "sans que tu les joignes à chaque tâche. Retirer de l'index ne supprime pas le fichier.")
    with st.form("ajout_doc", clear_on_submit=True):
        new = st.file_uploader("Ajouter un document", type=["pdf", "docx", "xlsx", "txt", "md", "csv"])
        if st.form_submit_button("Ajouter et indexer") and new:
            res = api("POST", "/documents", files={"file": (new.name, new.getvalue())})
            if res:
                st.success(f"{res['name']} : {res['chunks_indexed']} morceau(x) indexé(s).")
    docs = api("GET", "/documents") or []
    if not docs:
        st.info("La bibliothèque est vide.")
    for d in docs:
        cols = st.columns([5, 2, 2, 2])
        cols[0].write(f"📄 {d['name']} ({d['size_kb']} Ko)")
        cols[1].write("✅ indexé" if d["indexed"] else "— non indexé")
        if cols[2].button("Réindexer", key=f"re-{d['name']}"):
            api("POST", f"/documents/{d['name']}/index")
            st.rerun()
        if d["indexed"] and cols[3].button("Retirer de l'index", key=f"rm-{d['name']}"):
            api("DELETE", f"/documents/{d['name']}/index")
            st.rerun()


# ---------------------------------------------------------------------------------- Avis
elif page == "Avis":
    st.header("Avis sur les rapports")
    items = api("GET", "/feedback") or []
    if not items:
        st.info("Aucun avis pour l'instant. Note les rapports depuis la page Suivi.")
    else:
        up = sum(1 for i in items if i["rating"] > 0)
        c1, c2 = st.columns(2)
        c1.metric("👍", up)
        c2.metric("👎", len(items) - up)
        st.caption("Pour transformer les 👎 en pistes d'amélioration : `python scripts/feedback_report.py`")
        for i in items:
            st.write(f"{'👍' if i['rating'] > 0 else '👎'} `{i['task_id']}` — {i['section']} — {i['comment'] or ''}")
