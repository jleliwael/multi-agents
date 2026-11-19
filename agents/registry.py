"""Registre central des agents.

Un seul endroit décide quels outils et quel modèle reçoit chaque agent.
- Les agents de base (reader, researcher, analyst, coder, writer, critic) sont décrits
  dans BUILTIN_AGENTS.
- Ajouter un agent = déposer un fichier YAML dans agents/definitions/ :

    name: traducteur
    role: Traducteur de sources
    model: planner          # planner | coder | nom exact d'un modèle Ollama
    tools: [read_document_pages, fetch_page]
    prompt: |
      Tu es le Traducteur...

  Le fichier est chargé automatiquement ; un YAML peut aussi remplacer un agent de base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from config import settings
from agents.base import Agent
from llm.model_resolver import resolve_model

# L'import de ces modules enregistre leurs outils dans tools.registry
import tools.calculator  # noqa: F401
import tools.citations  # noqa: F401
import tools.code_runner  # noqa: F401
import tools.datetime_tool  # noqa: F401
import tools.documents  # noqa: F401
import tools.fetch_page  # noqa: F401
import tools.files  # noqa: F401
import tools.memory_search  # noqa: F401
import tools.web_search  # noqa: F401

DEFINITIONS_DIR: Path = settings.base_dir / "agents" / "definitions"


@dataclass
class AgentSpec:
    """Description d'un agent : rôle, outils autorisés et modèle."""
    name: str
    role: str
    tools: List[str] = field(default_factory=list)
    model: str = "planner"  # "planner", "coder" ou nom de modèle Ollama
    prompt: Optional[str] = None  # texte du prompt (sinon agents/prompts/<name>.md)
    source: str = "builtin"


BUILTIN_AGENTS: Dict[str, AgentSpec] = {
    "reader": AgentSpec(
        name="reader", role="Lecteur de documents et de la mémoire",
        tools=["read_document_pages", "read_file", "list_files", "memory_search"],
    ),
    "researcher": AgentSpec(
        name="researcher", role="Chercheur web documentaire",
        tools=["web_search", "fetch_page", "get_current_datetime"],
    ),
    "analyst": AgentSpec(
        name="analyst", role="Analyste et comparateur",
        tools=["calculator", "read_document_pages", "memory_search"],
    ),
    "coder": AgentSpec(
        name="coder", role="Codeur Python en bac à sable",
        tools=["code_runner", "calculator"], model="coder",
    ),
    "writer": AgentSpec(
        name="writer", role="Rédacteur de rapports Markdown", tools=["write_file"],
    ),
    "critic": AgentSpec(
        name="critic", role="Critique et assurance qualité", tools=[],
    ),
}

# Agent générique si le planificateur invente un nom inconnu
GENERIC_SPEC = AgentSpec(
    name="generalist", role="Agent généraliste",
    tools=["read_document_pages", "memory_search", "calculator"],
)


def _load_yaml_specs(folder: Optional[Path] = None) -> Dict[str, AgentSpec]:
    """Charge les agents décrits dans agents/definitions/*.yaml (fichiers invalides ignorés)."""
    folder = folder or DEFINITIONS_DIR
    specs: Dict[str, AgentSpec] = {}
    if not folder.exists():
        return specs
    for path in sorted(folder.glob("*.y*ml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            name = str(data["name"]).strip().lower()
            specs[name] = AgentSpec(
                name=name,
                role=str(data.get("role", f"Agent {name}")),
                tools=[str(t) for t in data.get("tools", []) or []],
                model=str(data.get("model", "planner")),
                prompt=data.get("prompt"),
                source=path.name,
            )
        except Exception as exc:  # un YAML cassé ne doit pas bloquer le système
            print(f"[registry] Définition d'agent ignorée ({path.name}) : {exc}")
    return specs


def all_specs() -> Dict[str, AgentSpec]:
    """Agents de base + agents YAML (le YAML l'emporte en cas de même nom)."""
    specs = dict(BUILTIN_AGENTS)
    specs.update(_load_yaml_specs())
    return specs


def _model_for(spec: AgentSpec, override: Optional[str]) -> str:
    if override:
        return resolve_model(override)
    if spec.model == "coder":
        return resolve_model(settings.model_coder)
    if spec.model == "planner":
        return resolve_model(settings.model_planner)
    return resolve_model(spec.model)


def create_agent(name: str, model: Optional[str] = None, llm_client: Optional[Any] = None) -> Agent:
    """Crée l'agent demandé avec ses outils et son modèle."""
    key = (name or "").strip().lower()
    specs = all_specs()
    spec = specs.get(key, GENERIC_SPEC)
    agent = Agent(
        name=spec.name if key in specs else (key or spec.name),
        role=spec.role,
        model=_model_for(spec, model),
        tools=list(spec.tools),
        llm_client=llm_client,
    )
    if spec.prompt:
        agent.system_prompt = str(spec.prompt).strip()
    return agent


def make_agent_factory(model: Optional[str] = None, llm_client: Optional[Any] = None) -> Callable[[str], Agent]:
    """Fabrique utilisée par l'orchestrateur : nom d'agent -> instance d'Agent."""
    def factory(agent_name: str) -> Agent:
        return create_agent(agent_name, model=model, llm_client=llm_client)
    return factory


def available_agent_names() -> List[str]:
    """Noms des agents disponibles (pour le prompt du planificateur et l'interface)."""
    return sorted(all_specs().keys())
