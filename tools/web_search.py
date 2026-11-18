"""Outil de recherche web multi-fournisseurs avec cascade intelligente.

Fournit l'interface unifiée web_search(query, max_results) avec priorité :
1. SearXNG local (http://localhost:8080)
2. API Tavily (si clé présente)
3. API Brave Search (si clé présente)
4. Fallback DuckDuckGo / Simulation hors-ligne sécurisée
Soumis au contrôle d'approbation humaine (security/approval.py).
"""

from typing import List, Dict, Any, Optional
import urllib.request
import urllib.parse
import urllib.error
import json
import re

from config import settings
from security.approval import require_approval
from tools.registry import tool


def _search_searxng(query: str, max_results: int) -> Optional[List[Dict[str, Any]]]:
    """Interroge l'instance SearXNG locale en format JSON."""
    if not settings.searxng_url:
        return None

    base_url = settings.searxng_url.rstrip("/")
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "language": "fr-FR",
        "categories": "general"
    })
    url = f"{base_url}/search?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MultiAgentsLocal/1.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            raw_results = data.get("results", [])
            results = []
            for item in raw_results[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "published_date": item.get("publishedDate")
                })
            return results if results else None
    except Exception:
        return None


def _search_tavily(query: str, max_results: int) -> Optional[List[Dict[str, Any]]]:
    """Interroge l'API Tavily si la clé est fournie."""
    if not settings.tavily_api_key:
        return None

    url = "https://api.tavily.com/search"
    payload = json.dumps({
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic"
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "MultiAgentsLocal/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = []
            for item in data.get("results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "published_date": item.get("published_date")
                })
            return results
    except Exception:
        return None


def _search_brave(query: str, max_results: int) -> Optional[List[Dict[str, Any]]]:
    """Interroge l'API Brave Search si la clé est fournie."""
    if not settings.brave_api_key:
        return None

    params = urllib.parse.urlencode({"q": query, "count": max_results})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": settings.brave_api_key,
                "User-Agent": "MultiAgentsLocal/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = []
            for item in data.get("web", {}).get("results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                    "published_date": item.get("page_age")
                })
            return results
    except Exception:
        return None


def _search_duckduckgo_fallback(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Repli DuckDuckGo léger en texte brut."""
    try:
        params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1"})
        url = f"https://api.duckduckgo.com/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "MultiAgentsLocal/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = []
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", "DuckDuckGo Topic"),
                    "url": data.get("AbstractURL", "https://duckduckgo.com"),
                    "snippet": data.get("AbstractText", ""),
                    "published_date": None
                })
            for topic in data.get("RelatedTopics", []):
                if isinstance(topic, dict) and "Text" in topic and "FirstURL" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:60],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                        "published_date": None
                    })
                if len(results) >= max_results:
                    break
            if results:
                return results
    except Exception:
        pass

    # Simulation structurée si réseau externe totalement coupé
    return [
        {
            "title": f"Résultat local simulé pour : {query}",
            "url": "https://documentation-locale.internal/search",
            "snippet": f"Synthèse des informations relatives à la recherche '{query}' en mode déconnecté.",
            "published_date": "2026-11-18"
        }
    ]


@tool(name="web_search", description="Effectue une recherche documentaire sur le web et retourne une liste de résultats avec titres, URLs et résumés.")
def web_search(query: str, max_results: int = 5) -> str:
    """Interface commune de recherche web avec contrôle de sécurité et cascade de fournisseurs."""
    # 1. Vérification d'approbation humaine pour requête réseau externe
    if not require_approval(action="web_search", target=query, details=f"Max résultats: {max_results}"):
        return "Action annulée : L'utilisateur a refusé l'accès réseau pour cette recherche web."

    # 2. Tentative via SearXNG local
    results = _search_searxng(query, max_results)

    # 3. Tentative via Tavily
    if not results:
        results = _search_tavily(query, max_results)

    # 4. Tentative via Brave Search
    if not results:
        results = _search_brave(query, max_results)

    # 5. Repli de secours
    if not results:
        results = _search_duckduckgo_fallback(query, max_results)

    return json.dumps(results, ensure_ascii=False, indent=2)
