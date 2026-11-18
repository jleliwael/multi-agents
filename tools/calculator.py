"""Outil de calcul arithmétique déterministe et sécurisé.

Évalue une expression mathématique via l'analyseur syntaxique standard (ast)
sans AUCUN recours à la fonction eval().
"""

import ast
import operator
import math
from typing import Union, Dict, Callable
from tools.registry import tool

# Opérateurs binaires autorisés
OPERATORS_BINAIRES: Dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Opérateurs unaires autorisés
OPERATORS_UNAIRES: Dict[type, Callable] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Fonctions mathématiques sûres autorisées
SAFE_FUNCTIONS: Dict[str, Callable] = {
    "sqrt": math.sqrt,
    "round": round,
    "abs": abs,
    "min": min,
    "max": max,
    "pow": math.pow,
    "ceil": math.ceil,
    "floor": math.floor,
}


def _eval_node(node: ast.AST) -> Union[int, float]:
    """Évalue récursivement un nœud de l'arbre syntaxique abstrait."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Type de constante non supporté : {type(node.value)}")

    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in OPERATORS_BINAIRES:
            raise ValueError(f"Opérateur binaire non autorisé : {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return OPERATORS_BINAIRES[op_type](left, right)

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in OPERATORS_UNAIRES:
            raise ValueError(f"Opérateur unaire non autorisé : {op_type.__name__}")
        operand = _eval_node(node.operand)
        return OPERATORS_UNAIRES[op_type](operand)

    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Appel de fonction complexe interdit")
        func_name = node.func.id
        if func_name not in SAFE_FUNCTIONS:
            raise ValueError(f"Fonction '{func_name}' non autorisée")
        args = [_eval_node(arg) for arg in node.args]
        return SAFE_FUNCTIONS[func_name](*args)

    raise ValueError(f"Expression non autorisée ou invalide : {type(node).__name__}")


@tool(name="calculator", description="Effectue un calcul mathématique exact et sécurisé (ex: '150 * 1.20', 'sqrt(16) + 4').")
def calculate(expression: str) -> str:
    """Calcule le résultat d'une expression mathématique sans eval."""
    try:
        # Nettoyage et parsing en mode expression
        clean_expr = expression.strip().replace(",", ".")
        tree = ast.parse(clean_expr, mode="eval")
        result = _eval_node(tree)
        # Formatage propre des entiers vs flottants
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(round(result, 6))
    except ZeroDivisionError:
        return "Erreur : Division par zéro impossible."
    except Exception as e:
        return f"Erreur de calcul sur '{expression}' : {str(e)}"
