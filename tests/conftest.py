"""Configuration des tests et simulateur de LLM factice (Mock LLM).

Permet d'exécuter l'ensemble de la suite de tests de manière 100% déterministe
et instantanée, sans dépendre du serveur Ollama ni consommer de VRAM.
"""

from typing import List, Dict, Any, Optional
from llm.ollama_llm import OllamaResponse


class MockOllamaLLM:
    """Simulateur de client LLM pour tests unitaires."""

    def __init__(self, responses_sequence: Optional[List[Dict[str, Any]]] = None):
        """Initialise le simulateur avec une séquence prédéfinie de réponses."""
        self.call_history: List[Dict[str, Any]] = []
        self.responses_sequence = responses_sequence or []
        self._call_count = 0

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2
    ) -> OllamaResponse:
        self.call_history.append({"messages": messages, "tools": tools})

        if self._call_count < len(self.responses_sequence):
            resp_data = self.responses_sequence[self._call_count]
            self._call_count += 1
            return OllamaResponse(
                message=resp_data.get("message", {}),
                raw_data=resp_data
            )

        # Comportement par défaut : synthèse textuelle directe
        last_user = messages[-1].get("content", "")
        return OllamaResponse(
            message={
                "role": "assistant",
                "content": f"[Mock LLM Response] Traitement achevé pour : {last_user[:50]}..."
            },
            raw_data={"eval_count": 25, "prompt_eval_count": 100, "total_duration": 500000000}
        )
