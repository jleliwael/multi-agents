"""Outil de téléchargement et d'extraction de contenu de pages web.

Télécharge une page HTTP/HTTPS, extrait son texte principal via Trafilatura,
conserve l'URL, le titre et la date, et applique des règles strictes de sécurité :
- Rejet des extensions exécutables dangereuses (.exe, .bat, .ps1, .msi, etc.)
- Rejet des fichiers volumineux (> 5 Mo)
- Contrôle d'approbation humaine.
"""

from typing import Dict, Any, Optional
import urllib.request
import urllib.parse
import urllib.error
import json
import re

from config import settings
from security.approval import require_approval
from tools.registry import tool

# Extensions interdites
DANGEROUS_EXTENSIONS = (
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".msi", ".dll", ".bin",
    ".sh", ".com", ".scr", ".pif", ".application", ".gadget"
)

MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 Mo maximum


@tool(name="fetch_page", description="Télécharge une page web de manière sécurisée et en extrait le texte principal dépouillé de toute publicité.")
def fetch_page(url: str) -> str:
    """Télécharge une URL et extrait son contenu structuré."""
    clean_url = url.strip()

    # 1. Vérification d'extension dangereuse
    parsed = urllib.parse.urlparse(clean_url)
    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in DANGEROUS_EXTENSIONS):
        return f"Erreur de sécurité : Téléchargement refusé. L'extension du fichier est considérée comme dangereuse ({path_lower})."

    # 2. Vérification d'approbation humaine
    if not require_approval(action="fetch_page", target=clean_url):
        return "Action annulée : L'utilisateur a refusé le téléchargement de cette page web."

    # 3. Requête HTTP avec contrôle de taille
    try:
        req = urllib.request.Request(
            clean_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) MultiAgents/1.0",
                "Accept": "text/html,application/xhtml+xml,text/plain"
            }
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            content_length = response.headers.get("Content-Length")

            if content_length and int(content_length) > MAX_SIZE_BYTES:
                return f"Erreur : Le fichier dépasse la taille maximale autorisée de 5 Mo ({content_length} octets)."

            # Lecture limitée pour se prémunir des bombes de données
            raw_data = response.read(MAX_SIZE_BYTES + 1)
            if len(raw_data) > MAX_SIZE_BYTES:
                return "Erreur : La taille de la page dépasse la limite de 5 Mo."

            html_content = raw_data.decode("utf-8", errors="replace")

        # 4. Extraction du texte via trafilatura
        title = ""
        date = None
        extracted_text = ""

        try:
            import trafilatura
            # Extraction fine avec métadonnées
            extracted = trafilatura.bare_extraction(html_content, url=clean_url)
            if extracted:
                title = extracted.title or ""
                date = extracted.date
                extracted_text = extracted.text or ""
            else:
                extracted_text = trafilatura.extract(html_content) or ""
        except ImportError:
            # Fallback regex si trafilatura n'est pas disponible
            title_match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            extracted_text = re.sub(r"<[^>]+>", " ", html_content)
            extracted_text = re.sub(r"\s+", " ", extracted_text).strip()

        if not extracted_text:
            return f"Avertissement : Aucun texte principal n'a pu être extrait de la page '{clean_url}'."

        result = {
            "url": clean_url,
            "title": title or "Titre non disponible",
            "date": date or "Date inconnue",
            "content_preview": extracted_text[:1500] + ("..." if len(extracted_text) > 1500 else ""),
            "total_chars": len(extracted_text)
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except urllib.error.HTTPError as he:
        return f"Erreur HTTP {he.code} lors du téléchargement de '{clean_url}' : {he.reason}"
    except Exception as e:
        return f"Erreur lors de la récupération de la page '{clean_url}' : {type(e).__name__} - {str(e)}"
