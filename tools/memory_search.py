"""Outil de recherche sémantique dans la mémoire long terme (ChromaDB).

Permet à l'agent Lecteur d'interroger la base vectorielle locale
et de récupérer les passages documentaires les plus pertinents avec leurs sources.
"""

from typing import List, Dict, Any
import json
from memory.long_term import long_term_memory
from tools.registry import tool


@tool(name="memory_search", description="Effectue une recherche sémantique (RAG) dans la mémoire documentaire locale ChromaDB et retourne les passages les plus pertinents.")
def memory_search(query: str, top_k: int = 5) -> str:
    """Interroge ChromaDB pour retrouver les extraits de documents les plus proches du sujet."""
    matches = long_term_memory.search_similar(query=query, top_k=top_k)

    if not matches:
        return f"Aucun passage pertinent trouvé dans la mémoire locale pour la requête : '{query}'."

    formatted_results = []
    for idx, m in enumerate(matches, 1):
        meta = m.get("metadata", {})
        source_name = meta.get("source_file", "inconnu")
        page_num = meta.get("page_number", 1)
        score = m.get("score", 0.0)
        text = m.get("text", "")

        formatted_results.append({
            "rang": idx,
            "source_file": source_name,
            "page_number": page_num,
            "score_similarite": score,
            "extrait": text
        })

    return json.dumps(formatted_results, ensure_ascii=False, indent=2)
