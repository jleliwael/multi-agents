"""Agent Rédacteur (Writer).

Rédige le rapport final en Markdown à partir des gabarits (templates),
intègre les renvois numérotés [1], [2]... vers les sources certifiées,
et enregistre le document dans data/reports/<date>_<task_id>.md.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import json
import re

from config import settings
from orchestrator.plan_models import Fact
from llm.ollama_llm import OllamaLLM
from tools.citations import CitationsManager


# Morceaux du prompt que certains modèles recopient à la fin de leur réponse
_ECHO_MARKERS = (
    "FAITS CERTIFIÉS DISPONIBLES", "ANALYSES PRÉCÉDENTES", "GABARIT DE STRUCTURE REQUIS",
    "[CONSIGNES DE RÉVISION", "Rédige le corps complet du rapport",
)
# Titre qui COMMENCE par Sources / Bibliographie / Références (ex. « ## 5. Sources et preuves »),
# mais pas « ## Analyse des sources de revenus »
_SOURCES_HEADING = re.compile(
    r"(?im)^#{1,6}\s*(?:\d+(?:\.\d+)*[.)]?\s*)?(?:sources|bibliographie|références|references)\b.*$"
)


def clean_report_body(body: str) -> str:
    """Retire du texte du modèle : le prompt recopié, ses balises de code et sa propre
    section « Sources » (souvent inventée) ; la table vérifiée est ajoutée ensuite."""
    text = body.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown|md)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    for marker in _ECHO_MARKERS:
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx]
    match = _SOURCES_HEADING.search(text)
    if match:
        text = text[:match.start()]
    # Lignes de la liste des faits recopiée telle quelle (« [1] ... (Source: x, Page 1 - Citation: ...) »)
    text = re.sub(r"(?m)^\s*\[\d+\][^\n]*\(Source\s*:[^\n]*Citation\s*:[^\n]*$\n?", "", text)
    return text.rstrip().rstrip("-").rstrip()


class WriterAgent:
    """Agent spécialisé dans la production éditoriale de rapports professionnels."""

    def __init__(self, model: Optional[str] = None, llm_client: Optional[Any] = None):
        self.model = model or settings.model_planner
        self.llm = llm_client or OllamaLLM(model=self.model)
        self.system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_file = settings.base_dir / "agents" / "prompts" / "writer.md"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8").strip()
        return "Tu es le Rédacteur. Rédige un rapport Markdown structuré avec citations précises [1], [2]."

    def _get_template_content(self, task_type: str) -> str:
        """Charge le gabarit Markdown adapté depuis agents/templates/."""
        clean_type = task_type.lower().strip()
        filename = "synthese.md"
        if "veille" in clean_type:
            filename = "veille.md"
        elif "comp" in clean_type:
            filename = "comparatif.md"
        elif "question" in clean_type:
            filename = "question.md"

        tpl_path = settings.base_dir / "agents" / "templates" / filename
        if tpl_path.exists():
            return tpl_path.read_text(encoding="utf-8")
        return "# Rapport d'Analyse : {{titre_mission}}\n\n## 1. Résumé\n{{resume_executif}}\n"

    def write_report(
        self,
        task_id: str,
        objective: str,
        task_type: str,
        facts: List[Fact],
        previous_outputs: Optional[Dict[str, Any]] = None,
        feedback: Optional[str] = None
    ) -> Tuple[str, Path]:
        """Rédige le rapport final, ajoute la table des sources et sauvegarde dans data/reports/."""
        # 1. Construction de la section des sources numérotées [1], [2]...
        sources_section, indexed_sources = CitationsManager.build_sources_section(facts)

        template = self._get_template_content(task_type)
        date_str = datetime.now().strftime("%d/%m/%Y")
        file_date = datetime.now().strftime("%Y%m%d")

        # Contexte préparé pour le modèle
        facts_summary = "\n".join(
            f"[{idx}] {f.assertion} (Source: {f.source_name}, {f.page_or_section} - Citation: « {f.exact_quote} »)"
            for idx, f in indexed_sources.items()
        )

        user_prompt = (
            f"Objectif : « {objective} »\n"
            f"Famille : {task_type}\n"
            f"Date : {date_str}\n\n"
            f"GABARIT DE STRUCTURE REQUIS :\n{template}\n\n"
            f"FAITS CERTIFIÉS DISPONIBLES (Utilise STRICTEMENT les renvois [1], [2], etc.) :\n{facts_summary}\n\n"
        )

        if previous_outputs:
            user_prompt += f"ANALYSES PRÉCÉDENTES :\n{json.dumps(previous_outputs, ensure_ascii=False, indent=2)}\n\n"

        if feedback:
            user_prompt += f"[CONSIGNES DE RÉVISION DU CRITIQUE] :\n{feedback}\n\n"

        user_prompt += (
            "Rédige le corps complet du rapport en respectant scrupuleusement le gabarit. "
            "Assure-toi d'insérer les renvois [1], [2] immédiatement après chaque affirmation clé."
        )

        # Inférence LLM
        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2
            )
            body = resp.content.strip()
        except Exception as exc:
            print(f"[Rédacteur] Modèle indisponible ({exc}) : rapport de secours à partir des faits.")
            # Rédaction de secours déterministe
            body = (
                f"# Rapport d'Analyse : {objective}\n\n"
                f"**Date** : {date_str}  \n**Statut** : Généré en local  \n\n"
                f"## 1. Synthèse Exécutive\n"
                f"L'analyse a porté sur l'objectif suivant : *{objective}*.\n\n"
                f"## 2. Points Clés Extraits\n"
            )
            for idx, f in indexed_sources.items():
                body += f"- [{idx}] {f.assertion}\n"

        # Nettoyage puis injection de la table des sources vérifiée
        full_report = clean_report_body(body) + "\n\n" + sources_section

        # Enregistrement dans data/reports/<date>_<task_id>.md
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        report_filename = f"{file_date}_{task_id}.md"
        report_path = settings.reports_dir / report_filename
        report_path.write_text(full_report, encoding="utf-8")

        return full_report, report_path
