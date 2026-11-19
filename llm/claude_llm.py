"""Option Claude (Phase 9) : planificateur et critique via l'API Anthropic.

Utilisé seulement si ANTHROPIC_API_KEY est renseignée dans le .env. Même interface
que OllamaLLM.chat(...) -> OllamaResponse, pour être injecté sans rien changer aux agents.
Si Claude échoue (réseau, quota, clé invalide), on bascule automatiquement sur Ollama.

⚠️ Confidentialité : avec une clé, l'objectif, les faits extraits et le rapport à vérifier
sont envoyés à Anthropic. Sans clé, tout reste sur le PC.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import settings
from llm.model_resolver import resolve_model
from llm.ollama_llm import OllamaLLM, OllamaResponse


class ClaudeLLM:
    """Client Claude (SDK officiel `anthropic`) au format OllamaLLM.

    Pas d'outils ici : le planificateur et le critique ne font que produire du JSON.
    """

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None,
                 max_tokens: int = 16000, effort: str = "medium"):
        import anthropic

        self.model = model or settings.claude_model
        self.max_tokens = max_tokens
        self.effort = effort
        self.client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key or None)

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
             temperature: float = 0.2) -> OllamaResponse:
        import anthropic

        # Format Anthropic : le prompt système va dans `system`, les tours dans `messages`.
        # `temperature` est ignorée : les modèles Claude récents la refusent.
        system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system" and m.get("content"))
        turns: List[Dict[str, Any]] = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                continue
            content = str(m.get("content") or "")
            if role == "tool":  # résultat d'outil (non utilisé ici) -> transmis comme texte
                role, content = "user", f"[Résultat d'outil]\n{content}"
            if role not in ("user", "assistant") or not content:
                continue
            turns.append({"role": role, "content": content})
        if not turns or turns[0]["role"] != "user":
            turns.insert(0, {"role": "user", "content": "Bonjour."})

        try:
            # Repli côté serveur si Claude décline la demande (refusal) : la requête est
            # rejouée sur un autre modèle Claude, choisi selon la catégorie du refus.
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system or anthropic.NOT_GIVEN,
                messages=turns,
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            raise ConnectionError("Clé ANTHROPIC_API_KEY invalide.") from exc
        except anthropic.RateLimitError as exc:
            raise ConnectionError("Quota Claude atteint (429).") from exc
        except anthropic.APIStatusError as exc:
            raise ConnectionError(f"Erreur de l'API Claude ({exc.status_code}) : {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ConnectionError("API Claude injoignable (réseau).") from exc

        if response.stop_reason == "refusal":
            raise ConnectionError("Claude a décliné la demande (refus) ; bascule sur Ollama.")

        text = "".join(block.text for block in response.content if block.type == "text")
        usage = response.usage
        return OllamaResponse(
            message={"role": "assistant", "content": text},
            raw_data={"eval_count": usage.output_tokens, "prompt_eval_count": usage.input_tokens},
        )


class FallbackLLM:
    """Essaie un premier client (Claude) puis un second (Ollama) en cas d'erreur."""

    def __init__(self, primary: Any, secondary: Any):
        self.primary = primary
        self.secondary = secondary
        self.model = getattr(primary, "model", "")

    def chat(self, messages, tools=None, temperature: float = 0.2) -> OllamaResponse:
        try:
            return self.primary.chat(messages=messages, tools=tools, temperature=temperature)
        except Exception as exc:
            print(f"[Claude] {exc} -> bascule sur Ollama.")
            return self.secondary.chat(messages=messages, tools=tools, temperature=temperature)


def claude_enabled() -> bool:
    return bool(settings.anthropic_api_key)


def make_reasoning_llm() -> Any:
    """Client pour le planificateur et le critique : Claude si une clé existe, sinon Ollama."""
    ollama = OllamaLLM(model=resolve_model(settings.model_planner))
    if not claude_enabled():
        return ollama
    try:
        return FallbackLLM(ClaudeLLM(), ollama)
    except Exception as exc:  # SDK absent ou clé illisible : on reste en local
        print(f"[Claude] désactivé ({exc}) -> Ollama.")
        return ollama
