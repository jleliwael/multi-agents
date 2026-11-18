"""Tests unitaires pour la classe Agent et la boucle d'exécution d'outils."""

import unittest
from agents.base import Agent
from tests.conftest import MockOllamaLLM
from tools.registry import ToolRegistry


class TestAgent(unittest.TestCase):

    def test_agent_tool_calling_loop(self):
        # Création d'un registre de test avec une fonction d'addition
        local_registry = ToolRegistry()

        @local_registry.register(name="add_numbers")
        def add(a: int, b: int) -> int:
            """Additionne deux entiers."""
            return a + b

        # Séquence simulée du LLM :
        # Étape 1 : Le LLM demande d'appeler add_numbers(a=12, b=8)
        # Étape 2 : Le LLM reçoit le résultat (20) et formule sa réponse finale
        mock_sequence = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "add_numbers",
                                "arguments": {"a": 12, "b": 8}
                            }
                        }
                    ]
                },
                "total_duration": 100000000
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "Le résultat du calcul est exactement 20."
                },
                "total_duration": 150000000
            }
        ]

        mock_llm = MockOllamaLLM(responses_sequence=mock_sequence)

        agent = Agent(
            name="tester",
            role="Testeur d'outils",
            tools=["add_numbers"],
            llm_client=mock_llm,
            tool_registry=local_registry
        )

        result = agent.run("Calcule la somme de 12 et 8.")
        self.assertEqual(result, "Le résultat du calcul est exactement 20.")
        self.assertEqual(len(mock_llm.call_history), 2)


if __name__ == "__main__":
    unittest.main()
