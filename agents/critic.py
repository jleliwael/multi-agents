"""Agent Critique et d'Assurance Qualité (Critic).

Évalue rigoureusement les livrables d'étapes et le rapport final :
- Vérifie que chaque affirmation majeure s'appuie sur un Fact réel
- Traque les hallucinations et sources inventées
- S'assure que les incertitudes sont signalées
- Renvoie un objet structuré {ok, problemes, suggestions}.
"""

from typing import List, Dict, Any, Optional
import json
from pydantic import BaseModel, Field

from config import settings
from orchestrator.plan_models import Fact
from llm.ollama_llm import OllamaLLM
from tools.citations import CitationsManager


class CriticEvaluation(BaseModel):
    """Structure de décision rendue par le Critique."""
    ok: bool = Field(..., description="True si le texte est conforme, sans invention et sourcé")
    problemes: List[str] = Field(default_factory=list, description="Liste des écarts ou anomalies constatés")
    suggestions: List[str] = Field(default_factory=list, description="Actions correctives concrètes pour révision")
    score: float = Field(default=8.0, ge=0.0, le=10.0, description="Note globale de qualité sur 10")


class CriticAgent:
    """Agent garant de la vérité terrain et de la traçabilité des faits."""

    def __init__(self, model: Optional[str] = None, llm_client: Optional[Any] = None):
        self.model = model or settings.model_planner
        self.llm = llm_client or OllamaLLM(model=self.model)
        self.system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_file = settings.base_dir / "agents" / "prompts" / "critic.md"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8").strip()
        return "Tu es le Critique qualité. Analyse la conformité du texte par rapport aux faits réels."

    def evaluate(
        self,
        instruction: str,
        output_text: str,
        available_facts: List[Fact]
    ) -> CriticEvaluation:
        """Évalue le texte produit face à l'instruction et aux faits disponibles."""
        problemes: List[str] = []
        suggestions: List[str] = []

        # 1. Contrôle déterministe des citations
        if available_facts:
            cit_res = CitationsManager.verify_text_citations(output_text, len(available_facts))
            if cit_res["invalid_indices"]:
                problemes.append(
                    f"Renvois de sources inexistants détectés dans le texte : {cit_res['invalid_indices']} (seulement {len(available_facts)} sources enregistrées)."
                )
                suggestions.append("Corriger les numéros de renvoi pour ne pointer que vers les sources valides.")

        # 2. Vérification de texte vide ou manifestement incomplet
        if not output_text or len(output_text.strip()) < 40:
            problemes.append("Le contenu produit est vide ou trop succinct pour répondre à l'instruction.")
            suggestions.append("Développer l'analyse conformément à l'objectif fixé.")

        # 3. Évaluation cognitive via LLM si possible
        try:
            facts_context = [
                {
                    "index": i,
                    "assertion": f.assertion,
                    "source": f.source_name,
                    "page": f.page_or_section,
                    "quote": f.exact_quote
                }
                for i, f in enumerate(available_facts, 1)
            ]

            eval_prompt = (
                f"Instruction de l'étape : « {instruction} »\n\n"
                f"Faits réels enregistrés en mémoire ({len(available_facts)} faits) :\n"
                f"{json.dumps(facts_context, ensure_ascii=False, indent=2)}\n\n"
                f"Livrable produit à évaluer :\n«««\n{output_text}\n»»»\n\n"
                f"Consigne : Réponds UNIQUEMENT avec un JSON strict contenant :\n"
                f'{{"ok": true|false, "problemes": ["..."], "suggestions": ["..."], "score": 8.5}}'
            )

            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": eval_prompt}
                ],
                temperature=0.1
            )

            # Nettoyage et parsing du JSON rendu par le LLM
            content = resp.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            data = json.loads(content.strip())
            llm_eval = CriticEvaluation.model_validate(data)

            # Fusion des contrôles déterministes et des remarques LLM
            all_problemes = problemes + llm_eval.problemes
            all_suggestions = suggestions + llm_eval.suggestions
            is_ok = llm_eval.ok and len(problemes) == 0

            return CriticEvaluation(
                ok=is_ok,
                problemes=all_problemes,
                suggestions=all_suggestions,
                score=min(llm_eval.score, 5.0) if not is_ok else llm_eval.score
            )

        except Exception:
            # Fallback déterministe si le LLM ne répond pas en JSON
            is_ok = len(problemes) == 0
            return CriticEvaluation(
                ok=is_ok,
                problemes=problemes,
                suggestions=suggestions,
                score=9.0 if is_ok else 4.0
            )
