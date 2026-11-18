"""Outil de construction, normalisation et vérification des citations de sources.

Permet d'associer des renvois numérotés [1], [2]... aux faits certifiés (Fact)
et de valider que chaque affirmation dans le texte final pointe vers une source réelle.
"""

from typing import List, Dict, Any, Tuple
import re
from orchestrator.plan_models import Fact
from tools.registry import tool


class CitationsManager:
    """Gestionnaire de table de sources et d'analyse des renvois bibliographiques."""

    @staticmethod
    def build_sources_section(facts: List[Fact]) -> Tuple[str, Dict[int, Fact]]:
        """Génère la section Markdown des sources et renvoie la table d'indexation."""
        if not facts:
            return "## Sources et Références\n\nAucune source externe enregistrée.\n", {}

        indexed_sources: Dict[int, Fact] = {}
        lines = [
            "## Sources et Références",
            "",
            "| # | Type | Source / Fichier | Page / Section | Extrait de Preuve | Fiabilité |",
            "| :- | :--- | :--- | :--- | :--- | :- |"
        ]

        # Déduplication basée sur la source et la citation
        seen = set()
        current_idx = 1

        for f in facts:
            key = (f.source_name, f.page_or_section, f.exact_quote[:50])
            if key in seen:
                continue
            seen.add(key)
            indexed_sources[current_idx] = f

            clean_quote = f.exact_quote.replace("\n", " ").strip()
            if len(clean_quote) > 80:
                clean_quote = clean_quote[:77] + "..."
            quote_display = f"« {clean_quote} »" if clean_quote else "—"
            page_display = f.page_or_section if f.page_or_section else "—"

            lines.append(
                f"| [{current_idx}] | {f.source_type.value} | `{f.source_name}` | {page_display} | {quote_display} | {f.confidence.value} |"
            )
            current_idx += 1

        lines.append("")
        return "\n".join(lines), indexed_sources

    @staticmethod
    def verify_text_citations(text: str, total_sources: int) -> Dict[str, Any]:
        """Vérifie que tous les renvois [N] du texte correspondent à des sources existantes."""
        # Recherche des motifs [1], [2], etc.
        raw_matches = re.findall(r"\[(\d+)\]", text)
        cited_indices = sorted(list(set(int(m) for m in raw_matches)))

        invalid_indices = [idx for idx in cited_indices if idx < 1 or idx > total_sources]
        missing_indices = [idx for idx in range(1, total_sources + 1) if idx not in cited_indices]

        has_valid_citations = len(cited_indices) > 0 and len(invalid_indices) == 0

        return {
            "is_valid": has_valid_citations or total_sources == 0,
            "cited_count": len(cited_indices),
            "cited_indices": cited_indices,
            "invalid_indices": invalid_indices,
            "missing_indices": missing_indices,
            "total_available_sources": total_sources
        }


@tool(name="verify_citations", description="Vérifie la validité des renvois [1], [2] dans un texte Markdown au regard du nombre de sources.")
def verify_citations_tool(text: str, total_sources: int) -> str:
    """Outil callable pour inspecter la cohérence bibliographique."""
    res = CitationsManager.verify_text_citations(text, total_sources)
    if res["is_valid"]:
        return f"Succès : {res['cited_count']} citations vérifiées sans aucune référence invalide."
    return f"Alerte Citations : Références invalides détectées {res['invalid_indices']} sur {total_sources} sources disponibles."
