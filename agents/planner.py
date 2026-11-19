"""Agent Planificateur (Planner).

Transforme un objectif utilisateur en plan d'action structuré (Plan)
validé par Pydantic, avec boucle de réessai automatique (2 tentatives)
et bascule vers un plan de secours déterministe (fallback).
"""

import json
from pathlib import Path
from typing import List, Optional, Any

from pydantic import ValidationError

from config import settings
from llm.ollama_llm import OllamaLLM
from orchestrator.plan_models import Plan
from orchestrator.fallback import get_fallback_plan


class PlannerAgent:
    """Agent spécialisé dans la planification stratégique de missions multi-agents."""

    def __init__(self, model: Optional[str] = None, llm_client: Optional[Any] = None):
        self.model = model or settings.model_planner
        self.llm = llm_client or OllamaLLM(model=self.model)
        self.system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_file = settings.base_dir / "agents" / "prompts" / "planner.md"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8").strip()
        return "Tu es le Planificateur d'un système multi-agents local. Génère un plan JSON strict."

    def _clean_json_text(self, text: str) -> str:
        """Nettoie le texte en retirant d'éventuelles balises markdown ```json."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def generate_plan(
        self,
        task_id: str,
        objective: str,
        files: Optional[List[str]] = None
    ) -> Plan:
        """Génère un plan validé par Pydantic avec gestion des erreurs et fallback."""
        user_prompt = f"Objectif : « {objective} »\n"
        if files:
            user_prompt += f"Fichiers d'entrée fournis : {json.dumps(files, ensure_ascii=False)}\n"
        user_prompt += f"Génère le plan d'action JSON avec task_id='{task_id}'."

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Inférence avec température basse pour respecter la grammaire JSON
                resp = self.llm.chat(messages=messages, temperature=0.1)
                clean_json = self._clean_json_text(resp.content)

                # Validation stricte via Pydantic
                parsed_data = json.loads(clean_json)
                if "task_id" not in parsed_data:
                    parsed_data["task_id"] = task_id
                if "objective" not in parsed_data:
                    parsed_data["objective"] = objective

                plan = Plan.model_validate(parsed_data)
                return plan

            except (json.JSONDecodeError, ValidationError, Exception) as err:
                if attempt < max_retries:
                    # Ajout de l'erreur au fil de discussion pour guidage du modèle
                    messages.append({"role": "assistant", "content": resp.content if 'resp' in locals() else ""})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Erreur de validation du JSON : {type(err).__name__} - {str(err)}. "
                            f"Corrige immédiatement et renvoie UNIQUEMENT un bloc JSON valide respectant les champs obligatoires : "
                            f"task_id, objective, task_type, et steps (id, agent, instruction, depends_on)."
                        )
                    })
                else:
                    # Échec après 2 réessais : bascule automatique vers le plan de secours
                    print(f"[FALLBACK] Échec de la génération JSON après {max_retries} réessais ({err}). Utilisation du plan de secours.")
                    return get_fallback_plan(task_id, objective, files)

        return get_fallback_plan(task_id, objective, files)
