"""Classe de base pour tous les agents du système.

Gère le chargement du prompt système, la boucle conversationnelle
avec Ollama, l'exécution des outils demandés et le contrôle strict de MAX_TOOL_CALLS.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import json

from config import settings
from llm.ollama_llm import OllamaLLM, OllamaResponse
from tools.registry import registry, ToolRegistry
from security.sanitizer import sanitize_external_content

# Outils dont le résultat est du contenu externe non fiable → désinfection obligatoire
_EXTERNAL_DATA_TOOLS: set[str] = {"web_search", "fetch_page", "read_document_pages"}


class Agent:
    """Agent autonome avec prompt système, modèle et boîte à outils dédiée."""

    def __init__(
        self,
        name: str,
        role: str,
        model: Optional[str] = None,
        tools: Optional[List[str]] = None,
        prompt_path: Optional[Path] = None,
        llm_client: Optional[Any] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.name = name
        self.role = role
        self.model = model or settings.model_planner
        self.tools = tools or []
        self.registry = tool_registry or registry
        self.llm = llm_client or OllamaLLM(model=self.model)

        # Chargement du prompt système
        self.system_prompt = self._load_prompt(prompt_path)

    def _load_prompt(self, custom_path: Optional[Path]) -> str:
        """Charge le prompt depuis agents/prompts/<name>.md ou chemin personnalisé."""
        if custom_path and custom_path.exists():
            return custom_path.read_text(encoding="utf-8").strip()

        default_path = settings.base_dir / "agents" / "prompts" / f"{self.name}.md"
        if default_path.exists():
            return default_path.read_text(encoding="utf-8").strip()

        return f"Tu es l'agent {self.name}, spécialisé dans le rôle : {self.role}."

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Exécute la mission confiée à l'agent avec boucle de rappel d'outils."""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

        # Contexte optionnel
        user_content = task
        if context:
            user_content += f"\n\n[Contexte de la tâche : {json.dumps(context, ensure_ascii=False)}]"
        messages.append({"role": "user", "content": user_content})

        # Schémas des outils autorisés pour cet agent
        tool_schemas = self.registry.get_schemas(self.tools) if self.tools else None

        iterations = 0
        max_iterations = settings.max_tool_calls

        while iterations < max_iterations:
            iterations += 1

            # Appel au LLM
            response: OllamaResponse = self.llm.chat(
                messages=messages,
                tools=tool_schemas,
                temperature=0.1
            )

            # Si le modèle ne demande pas d'outils, la réponse finale est prête
            if not response.has_tool_calls():
                return response.content

            # Ajout du message de l'assistant (avec ses tool_calls) à l'historique
            messages.append(response.message)

            # Exécution de chaque appel d'outil demandé
            for call in response.tool_calls:
                func_info = call.get("function", {})
                tool_name = func_info.get("name", "")
                tool_args = func_info.get("arguments", {})

                # Si l'outil n'est pas dans la liste autorisée de cet agent
                if self.tools and tool_name not in self.tools:
                    tool_output = f"Erreur de sécurité : L'agent '{self.name}' n'a pas l'autorisation d'utiliser l'outil '{tool_name}'."
                else:
                    tool_output = self.registry.execute(tool_name, tool_args)

                # Désinfection du contenu externe (anti-injection de prompt)
                if tool_name in _EXTERNAL_DATA_TOOLS:
                    tool_output = sanitize_external_content(
                        str(tool_output),
                        source=str(tool_args.get("filepath", tool_args.get("url", tool_args.get("query", tool_name))))
                    )

                # Renvoi du résultat de l'outil au modèle
                messages.append({
                    "role": "tool",
                    "content": str(tool_output)
                })

        # Si le quota d'appels d'outils est dépassé, on demande une synthèse finale
        messages.append({
            "role": "user",
            "content": f"Attention : Limite maximale de {max_iterations} appels d'outils atteinte. Rédige ta conclusion avec les données collectées."
        })
        final_resp = self.llm.chat(messages=messages, tools=None)
        return final_resp.content
