"""Client HTTP natif pour l'API locale Ollama.

Gère l'inférence conversationnelle (/api/chat) avec prise en charge
robuste du format d'appel d'outils (Tool Calling natif ou détecté dans le flux).
"""

from typing import List, Dict, Any, Optional
import json
import re
import urllib.request
import urllib.error
from config import settings


class OllamaResponse:
    """Réponse encapsulée d'un appel à Ollama."""

    def __init__(self, message: Dict[str, Any], raw_data: Dict[str, Any]):
        self.message = message
        self.raw_data = raw_data
        self.content: str = (message.get("content", "") or "").strip()
        self.tool_calls: List[Dict[str, Any]] = message.get("tool_calls", []) or []
        self.eval_count: int = raw_data.get("eval_count", 0)
        self.prompt_eval_count: int = raw_data.get("prompt_eval_count", 0)
        self.total_duration_sec: float = raw_data.get("total_duration", 0) / 1e9

        # Détection de secours si le modèle écrit l'appel d'outil directement en texte JSON
        if not self.tool_calls and self.content:
            self._try_parse_text_tool_calls()

    def _try_parse_text_tool_calls(self) -> None:
        """Détecte les appels d'outils formulés sous forme de texte brut JSON."""
        # Recherche d'un bloc JSON de type [{"name": ..., "arguments": ...}] ou {"name": ..., "arguments": ...}
        text = self.content.strip()
        if (text.startswith("[") and text.endswith("]")) or (text.startswith("{") and text.endswith("}")):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "name" in item:
                            self.tool_calls.append({
                                "function": {
                                    "name": item["name"],
                                    "arguments": item.get("arguments", {})
                                }
                            })
                elif isinstance(parsed, dict) and "name" in parsed:
                    self.tool_calls.append({
                        "function": {
                            "name": parsed["name"],
                            "arguments": parsed.get("arguments", {})
                        }
                    })
            except Exception:
                pass

    def has_tool_calls(self) -> bool:
        """Indique si le modèle a demandé un ou plusieurs appels d'outils."""
        return len(self.tool_calls) > 0


class OllamaLLM:
    """Client synchrone pour dialoguer avec Ollama en local."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.model_planner
        self.chat_url = f"{self.base_url.rstrip('/')}/api/chat"

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2
    ) -> OllamaResponse:
        """Envoie une requête de chat avec outils optionnels et retourne la réponse typée."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }

        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.chat_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                resp_json = json.loads(response.read().decode("utf-8"))
                return OllamaResponse(
                    message=resp_json.get("message", {}),
                    raw_data=resp_json
                )
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Impossible de contacter l'API Ollama à {self.chat_url} : {e}. "
                f"Vérifie qu'Ollama est lancé via 'ollama serve'."
            ) from e
