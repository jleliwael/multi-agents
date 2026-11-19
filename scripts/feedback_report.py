"""Rapport des avis utilisateurs (Phase 9) : transforme les 👎 en pistes d'amélioration.

    python scripts/feedback_report.py           # rapport dans la console + data/eval/avis_<date>.md
    python scripts/feedback_report.py --llm     # + propositions de modifications de prompts par le modèle

Regroupe les avis par famille de tâche et par section, repère les reproches fréquents
(trop court, sources, erreurs...) et indique quels fichiers de prompts/gabarits retoucher.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings  # noqa: E402

# Mots repérés dans les commentaires -> piste concrète
THEMES = {
    "trop court / pas assez détaillé": (["court", "succinct", "vague", "détail", "pauvre"],
                                        "Demander plus de détails chiffrés dans agents/prompts/writer.md et le gabarit."),
    "trop long": (["long", "verbeux", "bavard"], "Limiter la longueur dans agents/prompts/writer.md."),
    "sources manquantes ou douteuses": (["source", "page", "cit", "référence"],
                                        "Renforcer l'obligation de citer dans reader.md et writer.md."),
    "erreur / information fausse": (["faux", "erreur", "invent", "incorrect", "inexact"],
                                    "Vérifier le Lecteur (reader.md) et durcir les consignes du Critique (critic.md)."),
    "hors sujet": (["hors sujet", "répond pas", "pas la question"],
                   "Revoir le découpage du planificateur (planner.md) pour cette famille."),
    "mise en forme": (["forme", "tableau", "structure", "lisible"], "Ajuster le gabarit dans agents/templates/."),
}
TEMPLATE_FOR = {"synthese": "synthese.md", "veille": "veille.md", "comparatif": "comparatif.md", "question": "question.md"}


def themes_of(comment: str) -> List[str]:
    text = (comment or "").lower()
    return [name for name, (words, _) in THEMES.items() if any(w in text for w in words)]


def build_report(items: List[dict], tasks_by_id: Optional[Dict[str, dict]] = None) -> str:
    tasks_by_id = tasks_by_id or {}
    up = [i for i in items if i["rating"] > 0]
    down = [i for i in items if i["rating"] < 0]
    lines = [
        "# Rapport des avis utilisateurs",
        "",
        f"- Avis : **{len(items)}** (👍 {len(up)} / 👎 {len(down)})",
        f"- Satisfaction : **{round(100 * len(up) / len(items)) if items else 0} %**",
        "",
    ]
    if not down:
        lines.append("Aucun avis négatif : rien à corriger pour l'instant.")
        return "\n".join(lines) + "\n"

    by_family: Dict[str, List[dict]] = defaultdict(list)
    for i in down:
        by_family[tasks_by_id.get(i["task_id"], {}).get("family") or "inconnue"].append(i)

    theme_count: Counter = Counter()
    for i in down:
        theme_count.update(themes_of(i.get("comment", "")))

    lines += ["## Reproches les plus fréquents", ""]
    if theme_count:
        for theme, n in theme_count.most_common():
            lines.append(f"- **{theme}** ({n}) → {THEMES[theme][1]}")
    else:
        lines.append("- Aucun thème reconnu dans les commentaires (lis-les ci-dessous).")

    lines += ["", "## 👎 par famille de tâche", ""]
    for family, rows in sorted(by_family.items(), key=lambda kv: -len(kv[1])):
        sections = Counter(r.get("section") or "rapport" for r in rows)
        tpl = TEMPLATE_FOR.get(family)
        lines.append(f"### {family} — {len(rows)} avis négatif(s)")
        lines.append(f"Sections visées : {', '.join(f'{s} ({n})' for s, n in sections.most_common())}")
        if tpl:
            lines.append(f"Fichiers à revoir : `agents/templates/{tpl}`, `agents/prompts/writer.md`")
        for r in rows:
            objectif = tasks_by_id.get(r["task_id"], {}).get("objective", "")
            lines.append(f"- `{r['task_id']}` [{r.get('section') or 'rapport'}] « {r.get('comment') or '(sans commentaire)'} »"
                         + (f" — tâche : {objectif[:80]}" if objectif else ""))
        lines.append("")
    return "\n".join(lines) + "\n"


def llm_suggestions(report: str) -> str:
    """Demande au modèle des modifications concrètes de prompts (facultatif)."""
    from llm.claude_llm import make_reasoning_llm
    prompts = {p.name: p.read_text(encoding="utf-8")[:2500] for p in (BASE_DIR / "agents" / "prompts").glob("*.md")}
    resp = make_reasoning_llm().chat(messages=[
        {"role": "system", "content": "Tu améliores les prompts d'un système multi-agents. Propose des modifications "
                                      "précises (fichier, phrase à ajouter ou remplacer), 5 au maximum, en français."},
        {"role": "user", "content": f"Avis des utilisateurs :\n{report}\n\nPrompts actuels :\n{prompts}"},
    ])
    return resp.content


def main() -> int:
    parser = argparse.ArgumentParser(description="Rapport des avis 👍/👎")
    parser.add_argument("--llm", action="store_true", help="ajouter des propositions de prompts par le modèle")
    args = parser.parse_args()

    from storage.repository import feedback_repository, task_repository
    items = feedback_repository.list(limit=5000)
    tasks = {t.task_id: {"family": t.family, "objective": t.objective} for t in task_repository.list_tasks(limit=5000)}
    report = build_report(items, tasks)
    if args.llm and any(i["rating"] < 0 for i in items):
        report += "\n## Propositions de modifications (générées par le modèle — à relire)\n\n" + llm_suggestions(report) + "\n"

    settings.eval_dir.mkdir(parents=True, exist_ok=True)
    out = settings.eval_dir / f"avis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"Rapport enregistré : {out.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
