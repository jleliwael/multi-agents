"""Client HTTP natif pour l'API locale Ollama.

Gère l'inférence conversationnelle (/api/chat) avec prise en charge
robuste du format d'appel d'outils (Tool Calling natif ou détecté dans le flux).
Inclut un mécanisme de relance automatique à délai croissant (backoff exponentiel)
pour faire face aux surcharges temporaires d'Ollama ou aux erreurs réseau.
"""

from typing import List, Dict, Any, Optional
import json
import re
import time
import urllib.request
import urllib.error
from config import settings


# Délais de relance en secondes : 1re relance → 2s, 2e → 4s, 3e → 8s
RETRY_DELAYS_SECONDS: List[float] = [2.0, 4.0, 8.0]


class OllamaResponse:
    """Réponse encapsulée d'un appel à Ollama."""

    def __init__(self, message: Dict[str, Any], raw_data: Dict[str, Any]):
        self.message = message
        self.raw_data = raw_data
        # Retire un éventuel raisonnement <think>...</think> laissé dans la réponse
        raw_content = message.get("content", "") or ""
        self.content: str = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.S).strip()
        self.tool_calls: List[Dict[str, Any]] = message.get("tool_calls", []) or []
        self.eval_count: int = raw_data.get("eval_count", 0)
        self.prompt_eval_count: int = raw_data.get("prompt_eval_count", 0)
        self.total_duration_sec: float = raw_data.get("total_duration", 0) / 1e9

        # Détection de secours si le modèle écrit l'appel d'outil directement en texte JSON
        self.tool_calls_from_text: bool = False
        if not self.tool_calls and self.content:
            self._try_parse_text_tool_calls()

    def _try_parse_text_tool_calls(self) -> None:
        """Détecte les appels d'outils écrits en texte JSON au lieu du format natif.

        Certains modèles (ex. mistral) répondent par exemple :
            ```json
            [{"name": "read_document_pages", "arguments": {"filepath": "a.pdf"}}]
            ```
        On accepte : blocs de code, texte autour, objet seul ou liste,
        clés "arguments" / "parameters", forme {"function": {...}}, arguments en chaîne JSON.
        Un JSON de faits ({"facts": [...]}) n'est jamais pris pour un appel d'outil.
        """
        text = re.sub(r"```(?:json)?", "", self.content).strip()
        # On ne lit que la PREMIÈRE valeur JSON : certains modèles enchaînent ensuite de
        # faux « résultats d'outil » inventés, qu'il ne faut surtout pas croire.
        decoder = json.JSONDecoder()
        candidates = []
        starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
        for start in sorted(starts)[:1]:
            try:
                candidates.append(decoder.raw_decode(text, start)[0])
            except Exception:
                pass
        for parsed in candidates:
            items = parsed if isinstance(parsed, list) else [parsed]
            calls = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if isinstance(item.get("function"), dict):
                    item = item["function"]
                name = item.get("name")
                if not isinstance(name, str) or not name:
                    continue
                args = item.get("arguments", item.get("parameters", {}))
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                calls.append({"function": {"name": name, "arguments": args if isinstance(args, dict) else {}}})
            if calls:
                self.tool_calls.extend(calls)
                self.tool_calls_from_text = True
                return

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
        """Envoie une requête de chat avec outils optionnels et retourne la réponse typée.

        Relance automatiquement jusqu'à 3 fois en cas d'erreur transitoire,
        avec un délai doublant à chaque tentative (2s, 4s, 8s).
        """
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": settings.num_ctx,
                "num_predict": settings.max_output_tokens,
            }
        }
        # Le paramètre « think » n'est accepté que par les modèles qui raisonnent (qwen3...)
        if self.model.lower().startswith("qwen3"):
            payload["think"] = settings.ollama_think

        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        last_error: Exception = RuntimeError("Aucune tentative effectuée.")

        # Tentative initiale + relances avec backoff exponentiel
        for attempt, delay in enumerate([0.0] + RETRY_DELAYS_SECONDS):
            if delay > 0:
                print(f"[OllamaLLM] Relance #{attempt} dans {delay}s après erreur : {last_error}")
                time.sleep(delay)

            try:
                req = urllib.request.Request(
                    self.chat_url,
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=settings.ollama_timeout) as response:
                    resp_json = json.loads(response.read().decode("utf-8"))
                    return OllamaResponse(
                        message=resp_json.get("message", {}),
                        raw_data=resp_json
                    )

            except urllib.error.HTTPError as e:
                # 429 (trop de requêtes) et 503 (service indisponible) → relance
                if e.code in (429, 503):
                    last_error = ConnectionError(
                        f"Ollama occupé ou surchargé (HTTP {e.code}). "
                        f"Relance automatique prévue."
                    )
                    continue
                # Autres erreurs HTTP → échec immédiat (pas de relance)
                raise ConnectionError(
                    f"Erreur HTTP {e.code} de l'API Ollama à {self.chat_url}."
                ) from e

            except urllib.error.URLError as e:
                if isinstance(e.reason, TimeoutError):
                    raise ConnectionError(
                        f"Ollama n'a pas répondu en {settings.ollama_timeout}s. Augmente OLLAMA_TIMEOUT."
                    ) from e
                # Erreur réseau (Ollama non lancé, connexion refusée) → relance
                last_error = ConnectionError(
                    f"Impossible de contacter Ollama ({e}). "
                    f"Vérifie qu'Ollama est lancé via 'ollama serve'."
                )
                continue

            except TimeoutError as e:
                # Une génération trop longue ne sera pas plus rapide en la relançant
                raise ConnectionError(
                    f"Ollama n'a pas répondu en {settings.ollama_timeout}s (modèle trop lent pour ce prompt). "
                    f"Augmente OLLAMA_TIMEOUT ou réduis NUM_CTX / la taille des documents."
                ) from e

        # Toutes les tentatives ont échoué
        raise ConnectionError(
            f"Impossible de contacter l'API Ollama après {len(RETRY_DELAYS_SECONDS) + 1} tentatives. "
            f"Dernière erreur : {last_error}"
        ) from last_error
