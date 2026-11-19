"""Évaluation chiffrée du système multi-agents (Phase 7).

Lance les tâches de tests/eval/jeu_30_taches.json, note chaque rapport et produit :
- data/eval/<date>.json        : résultats détaillés (réutilisables pour --compare)
- docs/rapport_qualite.md      : rapport lisible (global, par famille, erreurs fréquentes)

Exemples :
    python scripts/evaluate.py                        # 29 tâches hors web
    python scripts/evaluate.py --web                  # + la tâche de veille web
    python scripts/evaluate.py --ids eval-01 eval-17  # seulement ces tâches
    python scripts/evaluate.py --famille question     # une famille
    python scripts/evaluate.py --juge                 # + note d'un LLM juge (plus lent)
    python scripts/evaluate.py --compare data/eval/20261119_101500.json
    python scripts/evaluate.py --simulation --limit 3 # test rapide sans Ollama

Notation automatique d'une tâche (score sur 100) :
- contenu (60)   : part des éléments attendus présents dans le rapport
- sources (20)   : nombre de sources >= minimum et documents attendus bien cités
- citations (10) : aucun renvoi [n] vers une source inexistante
- temps (10)     : durée <= temps maximum de la tâche
Une tâche est « réussie » si le contenu est complet, sans citation inventée,
et si la mission s'est terminée (statut COMPLETED).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings  # noqa: E402
from tools.citations import CitationsManager  # noqa: E402

JEU_FILE = BASE_DIR / "tests" / "eval" / "jeu_30_taches.json"
RAPPORT_FILE = BASE_DIR / "docs" / "rapport_qualite.md"
DEFAULT_TIME_LIMIT_S = 600


# --------------------------------------------------------------------------- notation
def normalize(text: str) -> str:
    """Minuscules, sans accents, apostrophes et espaces uniformisés."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("’", "'").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", text)


def contains(text_norm: str, variant: str) -> bool:
    """Vrai si la variante apparaît (les espaces sont ignorés pour les nombres : « 1 150 000 » = « 1150000 »)."""
    v = normalize(variant)
    if v in text_norm:
        return True
    return v.replace(" ", "") in text_norm.replace(" ", "")


def score_task(task: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule les critères automatiques d'une tâche à partir du résultat de l'orchestrateur."""
    attendu = task.get("attendu", {})
    report = run.get("final_output", "") or ""
    facts = run.get("facts", []) or []
    text = normalize(report)

    groups: List[List[str]] = attendu.get("doit_contenir", [])
    missing = [g for g in groups if not any(contains(text, v) for v in g)]
    contenu = 1.0 if not groups else (len(groups) - len(missing)) / len(groups)

    interdits = [w for w in attendu.get("interdit", []) if contains(text, w)]

    sources_min = int(attendu.get("sources_min", 1))
    cited_names = {normalize(str(f.get("source_name", ""))) for f in facts}
    expected_docs = attendu.get("sources_attendues", [])
    docs_missing = [
        d for d in expected_docs
        if not any(normalize(d) in name for name in cited_names) and not contains(text, d)
    ]
    sources_ok = len(facts) >= sources_min and not docs_missing

    citations = CitationsManager.verify_text_citations(report, len(facts)) if report else {"invalid_indices": []}
    invalid_citations = list(citations.get("invalid_indices", []))

    temps_max = int(task.get("temps_max_s", DEFAULT_TIME_LIMIT_S))
    temps_ok = run.get("duree_s", 0) <= temps_max

    score = round(
        60 * contenu * (0 if interdits else 1)
        + 20 * (1 if sources_ok else 0)
        + 10 * (0 if invalid_citations else 1)
        + 10 * (1 if temps_ok else 0),
        1,
    )
    reussie = (
        run.get("status") == "COMPLETED" and contenu == 1.0 and not interdits and not invalid_citations
    )
    return {
        "score": score,
        "reussie": reussie,
        "contenu": round(contenu, 2),
        "elements_manquants": [" / ".join(g) for g in missing],
        "interdits_trouves": interdits,
        "nb_sources": len(facts),
        "sources_ok": sources_ok,
        "documents_non_cites": docs_missing,
        "citations_inventees": invalid_citations,
        "temps_ok": temps_ok,
    }


# --------------------------------------------------------------------------- LLM juge
JUGE_GRILLE = """Tu es un évaluateur strict. Note le rapport sur 10 avec cette grille fixe :
- Exactitude (0-4) : les faits correspondent à la question, aucun chiffre inventé.
- Sources (0-3) : chaque affirmation importante renvoie à une source réelle.
- Clarté (0-2) : réponse directe, structurée, en français.
- Honnêteté (0-1) : signale clairement ce qui est introuvable ou incertain.
Réponds UNIQUEMENT en JSON : {"note": <0-10>, "justification": "<une phrase>"}"""


def llm_judge(task: Dict[str, Any], report: str) -> Dict[str, Any]:
    """Note le rapport avec le modèle du planificateur (grille fixe). Erreur -> note absente."""
    from llm.model_resolver import resolve_model
    from llm.ollama_llm import OllamaLLM

    llm = OllamaLLM(model=resolve_model(settings.model_planner))
    attendu = "; ".join(" ou ".join(g) for g in task.get("attendu", {}).get("doit_contenir", []))
    try:
        resp = llm.chat(messages=[
            {"role": "system", "content": JUGE_GRILLE},
            {"role": "user", "content": (
                f"Question : {task['objectif']}\nÉléments attendus : {attendu}\n\n"
                f"Rapport à noter :\n{report[:6000]}"
            )},
        ], temperature=0.0)
        match = re.search(r"\{.*\}", resp.content, re.S)
        data = json.loads(match.group(0)) if match else {}
        note = float(data.get("note"))
        return {"note": max(0.0, min(10.0, note)), "justification": str(data.get("justification", ""))[:300]}
    except Exception as exc:
        return {"note": None, "justification": f"Juge indisponible : {type(exc).__name__}"}


# --------------------------------------------------------------------------- exécution
def build_orchestrator(simulation: bool):
    """Orchestrateur réel, ou simulé (sans Ollama) pour vérifier le script rapidement."""
    from orchestrator.orchestrator import Orchestrator

    if not simulation:
        return Orchestrator()

    from agents.critic import CriticAgent
    from agents.planner import PlannerAgent
    from agents.writer import WriterAgent
    from storage.repository import TaskRepository
    from tests.conftest import MockOllamaLLM
    from tools.documents import extract_document

    class SimulatedReader:
        """Lit vraiment les documents de la tâche et renvoie chaque morceau comme un fait sourcé."""
        def __init__(self, name: str):
            self.name = name

        def run(self, task: str, context: Optional[dict] = None) -> str:
            if self.name != "reader":
                return "Étape simulée."
            facts = []
            for path in _SIMULATION_FILES:
                for chunk in extract_document(path)[:4]:
                    facts.append({
                        "assertion": chunk.content[:300], "source_type": "document",
                        "source_name": Path(path).name, "page_or_section": f"Page {chunk.page_number}",
                        "exact_quote": chunk.content[:120], "confidence": "haute",
                    })
            return json.dumps({"facts": facts}, ensure_ascii=False)

    sim_db = settings.eval_dir / "simulation.db"
    sim_db.parent.mkdir(parents=True, exist_ok=True)
    return Orchestrator(
        planner=PlannerAgent(llm_client=MockOllamaLLM()),  # réponse invalide -> plan de secours
        critic=CriticAgent(llm_client=MockOllamaLLM()),
        writer=WriterAgent(llm_client=MockOllamaLLM()),
        repository=TaskRepository(db_path=sim_db),
        agent_factory=SimulatedReader,
    )


# Fichiers de la tâche en cours (utilisés uniquement par le mode simulation)
_SIMULATION_FILES: List[str] = []


def run_task(orchestrator, task: Dict[str, Any], simulation: bool) -> Dict[str, Any]:
    files = [str(BASE_DIR / f) for f in task.get("fichiers", [])]
    objective = task["objectif"]
    _SIMULATION_FILES[:] = files
    t0 = time.time()
    try:
        res = orchestrator.run(objective=objective, task_id=f"{task['id']}-{int(t0)}", files=files)
        return {
            "status": res.get("status", "COMPLETED"), "final_output": res.get("final_output", ""),
            "facts": res.get("facts", []), "report_path": res.get("report_path", ""),
            "duree_s": round(time.time() - t0, 1), "erreur": res.get("limit_reason"),
        }
    except Exception as exc:
        return {"status": "FAILED", "final_output": "", "facts": [], "report_path": "",
                "duree_s": round(time.time() - t0, 1), "erreur": f"{type(exc).__name__} : {exc}"}


def select_tasks(all_tasks: List[Dict[str, Any]], args) -> List[Dict[str, Any]]:
    tasks = all_tasks
    if args.ids:
        tasks = [t for t in tasks if t["id"] in set(args.ids)]
    if args.famille:
        tasks = [t for t in tasks if t["famille"] == args.famille]
    if not args.web:
        tasks = [t for t in tasks if not t.get("web")]
    if args.limit:
        tasks = tasks[: args.limit]
    return tasks


# --------------------------------------------------------------------------- synthèse
def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    def stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        n = len(rows) or 1
        notes = [r["juge"]["note"] for r in rows if r.get("juge") and r["juge"].get("note") is not None]
        return {
            "taches": len(rows),
            "reussite_pct": round(100 * sum(r["eval"]["reussie"] for r in rows) / n, 1),
            "score_moyen": round(sum(r["eval"]["score"] for r in rows) / n, 1),
            "temps_moyen_s": round(sum(r["run"]["duree_s"] for r in rows) / n, 1),
            "citations_inventees": sum(len(r["eval"]["citations_inventees"]) for r in rows),
            "note_juge_moyenne": round(sum(notes) / len(notes), 1) if notes else None,
        }

    par_famille: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in results:
        par_famille[r["famille"]].append(r)

    erreurs: Counter = Counter()
    for r in results:
        e = r["eval"]
        if r["run"]["status"] != "COMPLETED":
            erreurs[f"Mission non terminée ({r['run']['status']})"] += 1
        if e["elements_manquants"]:
            erreurs["Éléments attendus absents du rapport"] += 1
        if not e["sources_ok"]:
            erreurs["Sources insuffisantes ou document non cité"] += 1
        if e["citations_inventees"]:
            erreurs["Renvoi [n] vers une source inexistante"] += 1
        if not e["temps_ok"]:
            erreurs["Temps maximum dépassé"] += 1
        if e["interdits_trouves"]:
            erreurs["Contenu interdit présent"] += 1

    return {
        "global": stats(results),
        "par_famille": {k: stats(v) for k, v in sorted(par_famille.items())},
        "erreurs_frequentes": erreurs.most_common(),
    }


def compare(current: Dict[str, Any], old_path: Path) -> List[str]:
    """Lignes Markdown comparant deux évaluations (global + tâche par tâche)."""
    old = json.loads(old_path.read_text(encoding="utf-8"))
    lines = [f"## Comparaison avec `{old_path.name}`", "", "| Indicateur | Avant | Après | Écart |", "|---|---|---|---|"]
    for key, label in [("reussite_pct", "Réussite (%)"), ("score_moyen", "Score moyen /100"),
                       ("temps_moyen_s", "Temps moyen (s)"), ("citations_inventees", "Citations inventées")]:
        a, b = old["synthese"]["global"].get(key), current["synthese"]["global"].get(key)
        delta = round(b - a, 1) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else "—"
        lines.append(f"| {label} | {a} | {b} | {delta:+} |" if delta != "—" else f"| {label} | {a} | {b} | — |")
    old_by_id = {r["id"]: r for r in old["resultats"]}
    changes = []
    for r in current["resultats"]:
        o = old_by_id.get(r["id"])
        if o and o["eval"]["reussie"] != r["eval"]["reussie"]:
            changes.append(f"- {r['id']} {r['titre']} : {'✅ réussie' if r['eval']['reussie'] else '❌ en échec'} (avant : {'réussie' if o['eval']['reussie'] else 'échec'})")
    lines += ["", "**Tâches qui ont changé :**", ""] + (changes or ["- aucune"])
    return lines


def write_markdown(payload: Dict[str, Any], comparison: Optional[List[str]]) -> str:
    s = payload["synthese"]
    g = s["global"]
    lines = [
        "# Rapport qualité — évaluation chiffrée",
        "",
        f"- **Date :** {payload['date'][:16].replace('T', ' ')} UTC",
        f"- **Modèle :** {payload['modele']}",
        f"- **Mode :** {'simulation (sans Ollama)' if payload['simulation'] else 'réel'}",
        f"- **Fichier de résultats :** `data/eval/{payload['fichier']}`",
        "",
        "## Résultat global",
        "",
        "| Tâches | Réussite | Score moyen | Temps moyen | Citations inventées | Note du juge |",
        "|---|---|---|---|---|---|",
        f"| {g['taches']} | {g['reussite_pct']} % | {g['score_moyen']}/100 | {g['temps_moyen_s']} s | "
        f"{g['citations_inventees']} | {g['note_juge_moyenne'] if g['note_juge_moyenne'] is not None else '—'} |",
        "",
        "## Par famille de tâche",
        "",
        "| Famille | Tâches | Réussite | Score moyen | Temps moyen |",
        "|---|---|---|---|---|",
    ]
    for fam, st in s["par_famille"].items():
        lines.append(f"| {fam} | {st['taches']} | {st['reussite_pct']} % | {st['score_moyen']}/100 | {st['temps_moyen_s']} s |")
    lines += ["", "## Erreurs les plus fréquentes", ""]
    lines += [f"- {e} : {n} tâche(s)" for e, n in s["erreurs_frequentes"]] or ["- aucune"]
    lines += ["", "## Détail par tâche", "", "| Tâche | Famille | Statut | Score | Durée | Problèmes |", "|---|---|---|---|---|---|"]
    for r in payload["resultats"]:
        e = r["eval"]
        pb = []
        if e["elements_manquants"]:
            pb.append("manque : " + "; ".join(e["elements_manquants"]))
        if e["documents_non_cites"]:
            pb.append("non cité : " + ", ".join(e["documents_non_cites"]))
        if e["citations_inventees"]:
            pb.append(f"renvois inventés {e['citations_inventees']}")
        if r["run"].get("erreur"):
            pb.append(str(r["run"]["erreur"])[:80])
        lines.append(
            f"| {r['id']} {r['titre']} | {r['famille']} | {'✅' if e['reussie'] else '❌'} {r['run']['status']} | "
            f"{e['score']} | {r['run']['duree_s']} s | {' ; '.join(pb).replace('|', '/') or '—'} |"
        )
    if comparison:
        lines += [""] + comparison
    lines += ["", "> Généré par `python scripts/evaluate.py`. Méthode de notation : voir l'en-tête du script.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Évaluation chiffrée du système multi-agents")
    parser.add_argument("--ids", nargs="*", help="identifiants de tâches à lancer")
    parser.add_argument("--famille", help="question, donnees, synthese, comparatif, traduction, robustesse, veille")
    parser.add_argument("--web", action="store_true", help="inclure les tâches qui demandent internet")
    parser.add_argument("--limit", type=int, help="nombre maximum de tâches")
    parser.add_argument("--juge", action="store_true", help="ajouter la note d'un LLM juge (grille fixe)")
    parser.add_argument("--compare", type=Path, help="fichier data/eval/<date>.json à comparer")
    parser.add_argument("--simulation", action="store_true", help="tester le script sans Ollama")
    parser.add_argument("--sans-rapport", action="store_true", help="ne pas réécrire docs/rapport_qualite.md")
    args = parser.parse_args()

    jeu = json.loads(JEU_FILE.read_text(encoding="utf-8"))
    tasks = select_tasks(jeu["taches"], args)
    if not tasks:
        print("Aucune tâche sélectionnée.")
        return 1

    from llm.model_resolver import resolve_model
    modele = "simulation" if args.simulation else resolve_model(settings.model_planner)
    print("=" * 78)
    print(f"  ÉVALUATION — {len(tasks)} tâche(s) — modèle : {modele}")
    print("=" * 78)

    orchestrator = build_orchestrator(args.simulation)
    results = []
    for i, task in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {task['id']} {task['titre']} ...", end=" ", flush=True)
        run = run_task(orchestrator, task, args.simulation)
        ev = score_task(task, run)
        juge = llm_judge(task, run["final_output"]) if args.juge and not args.simulation else None
        results.append({"id": task["id"], "titre": task["titre"], "famille": task["famille"],
                        "run": {k: v for k, v in run.items() if k not in ("final_output", "facts")},
                        "eval": ev, "juge": juge})
        print(f"{'OK ' if ev['reussie'] else 'KO '} score {ev['score']}/100 en {run['duree_s']} s")

    now = datetime.now()
    fichier = f"{now.strftime('%Y%m%d_%H%M%S')}{'_simulation' if args.simulation else ''}.json"
    payload = {
        "date": datetime.now(timezone.utc).isoformat(), "modele": modele, "simulation": args.simulation,
        "fichier": fichier, "resultats": results, "synthese": summarize(results),
    }
    settings.eval_dir.mkdir(parents=True, exist_ok=True)
    (settings.eval_dir / fichier).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    comparison = compare(payload, args.compare) if args.compare else None
    markdown = write_markdown(payload, comparison)
    if not args.sans_rapport:
        RAPPORT_FILE.write_text(markdown, encoding="utf-8")

    g = payload["synthese"]["global"]
    print("-" * 78)
    print(f"Réussite : {g['reussite_pct']} %  |  score moyen : {g['score_moyen']}/100  |  temps moyen : {g['temps_moyen_s']} s")
    print(f"Résultats : data/eval/{fichier}")
    if not args.sans_rapport:
        print(f"Rapport   : {RAPPORT_FILE.relative_to(BASE_DIR)}")
    if comparison:
        print("\n".join(comparison))
    return 0


if __name__ == "__main__":
    sys.exit(main())
