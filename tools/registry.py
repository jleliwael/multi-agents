"""Registre central des outils du système multi-agents.

Fournit le décorateur @tool pour enregistrer une fonction Python,
générer automatiquement son schéma de paramètres JSON compatible Ollama
et exécuter les outils de manière sécurisée.
"""

from typing import Callable, Dict, Any, List, Optional
import inspect
import json


class ToolDefinition:
    """Représentation structurée d'un outil enregistrable."""

    def __init__(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        self.description = description or (func.__doc__ or "").strip().split("\n")[0]
        self.schema = self._generate_ollama_schema()

    def _type_to_json_type(self, py_type: Any) -> str:
        """Convertit un type Python en type JSON Schema."""
        if py_type in (int,):
            return "integer"
        elif py_type in (float,):
            return "number"
        elif py_type in (bool,):
            return "boolean"
        elif py_type in (list, List):
            return "array"
        elif py_type in (dict, Dict):
            return "object"
        return "string"

    def _generate_ollama_schema(self) -> Dict[str, Any]:
        """Inspecte la signature de la fonction pour générer le schéma d'outils Ollama."""
        sig = inspect.signature(self.func)
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                param_type = self._type_to_json_type(param.annotation)

            properties[param_name] = {
                "type": param_type,
                "description": f"Paramètre {param_name}"
            }

            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }

    def execute(self, arguments: Dict[str, Any]) -> str:
        """Exécute la fonction avec les arguments fournis et formate la réponse en chaîne."""
        try:
            res = self.func(**arguments)
            if isinstance(res, (dict, list)):
                return json.dumps(res, ensure_ascii=False, indent=2)
            return str(res)
        except Exception as e:
            return f"Erreur lors de l'exécution de l'outil '{self.name}' : {type(e).__name__} - {str(e)}"


class ToolRegistry:
    """Gestionnaire central de tous les outils enregistrés."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, func: Optional[Callable] = None, *, name: Optional[str] = None, description: Optional[str] = None):
        """Enregistre un outil via le décorateur @tool."""
        def decorator(f: Callable) -> Callable:
            tool_def = ToolDefinition(f, name=name, description=description)
            self._tools[tool_def.name] = tool_def
            return f

        if func is None:
            return decorator
        return decorator(func)

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Récupère la définition d'un outil par son nom."""
        return self._tools.get(name)

    def get_schemas(self, tool_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Retourne la liste des schémas d'outils au format Ollama."""
        if tool_names is None:
            return [t.schema for t in self._tools.values()]
        return [self._tools[name].schema for name in tool_names if name in self._tools]

    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """Exécute un outil par son nom."""
        tool = self.get_tool(name)
        if not tool:
            return f"Erreur : Outil '{name}' inconnu dans le registre."
        return tool.execute(arguments)


# Registre global d'outils
registry = ToolRegistry()
tool = registry.register
