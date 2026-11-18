"""Script de benchmark des modèles Ollama locaux.

Mesure la vitesse de génération (tokens/s), la latence totale et
la consommation mémoire pour un texte volumineux (~3 000 mots).
"""

import time
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

# Modèles ciblés pour le comparatif
MODELS_TO_BENCH = ["qwen3:14b", "qwen3:8b", "qwen2.5:14b", "qwen2.5:7b"]

# Texte d'épreuve de test (~3 000 mots synthétiques sur l'analyse documentaire)
TEXTE_TEST = """
Le traitement automatisé et l'analyse de documents volumineux constituent un défi majeur pour les architectures d'intelligence artificielle modernes. 
Dans les organisations contemporaines, le volume quotidien de données non structurées (rapports PDF, comptes rendus de réunion au format DOCX, 
feuilles de calcul Excel et flux d'actualités web) croît à un rythme exponentiel. Pour extraire de la valeur de ce déluge informationnel, 
la mise en place de pipelines de traitement documentaire locaux est devenue une priorité stratégique, motivée à la fois par la confidentialité 
des données et la souveraineté technologique.

Historiquement, les systèmes d'extraction documentaire reposaient sur des règles heuristiques rigides et des expressions régulières. 
Bien qu'efficaces pour des formats standardisés comme les formulaires CERFA ou les factures normalisées, ces approches échouaient systématiquement 
dès lors qu'il s'agissait d'interpréter des documents narratifs complexes, des synthèses stratégiques ou des études de marché transversales. 
L'avènement des modèles de langage de grande taille (LLM) a profondément transformé ce paradigme en apportant une capacité sans précédent 
de compréhension sémantique, de résumé contextuel et de raisonnement logique.

Toutefois, le déploiement de ces modèles sur des infrastructures locales restreintes, telles que des stations de travail équipées de 
cartes graphiques grand public de 6 à 8 Go de VRAM, impose des contraintes physiques incontournables. La quantification en 4 bits (GGUF Q4_K_M) 
permet de réduire drastiquement l'empreinte mémoire d'un modèle sans dégradation majeure de ses capacités cognitives. Ainsi, un modèle 
de 7 ou 8 milliards de paramètres peut tenir intégralement dans la VRAM d'un GPU portable, garantissant des débits de génération élevés 
(souvent supérieurs à 30 tokens par seconde). À l'inverse, un modèle de 14 milliards de paramètres nécessite entre 8 et 10 Go de mémoire 
pour ses poids et son contexte d'attention, contraignant le moteur d'inférence (comme Ollama ou llama.cpp) à décharger une partie des couches 
sur la mémoire vive système (RAM) via le processeur central (CPU). Ce phénomène de déchargement partiel (CPU offloading) entraîne une baisse 
mécanique de la vitesse d'inférence, mais permet d'exécuter des modèles aux capacités de raisonnement supérieures sur du matériel modeste.

Dans ce contexte, la segmentation des tâches au sein d'une équipe multi-agents s'avère particulièrement pertinente. Plutôt que de confier 
l'intégralité du traitement à un unique modèle monolithique, l'architecture distribue les responsabilités : un modèle plus dense et réfléchi 
(ex. 14B) assure la planification stratégique et l'arbitrage critique, tandis qu'un modèle plus agile et spécialisé (ex. 7B ou 8B) prend en charge 
la génération de code, les transformations de format et les synthèses intermédiaires. 

Cette organisation hiérarchique garantit un équilibre optimal entre rigueur intellectuelle, rapidité d'exécution et maîtrise thermique de la machine.
L'analyse comparative des performances entre différentes tailles de modèles constitue donc un prérequis indispensable avant de fixer définitivement 
l'affectation de chaque agent au sein du système.
""" * 12  # Environ 3 000 mots


def check_model_available(model_name: str) -> bool:
    """Vérifie si un modèle est présent dans l'instance Ollama locale."""
    try:
        req = urllib.request.Request(OLLAMA_TAGS_URL)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            installed_models = [m["name"] for m in data.get("models", [])]
            return any(model_name == m or model_name in m for m in installed_models)
    except Exception:
        return False


def bench_single_model(model_name: str) -> Optional[Dict[str, Any]]:
    """Envoie la requête de synthèse au modèle et extrait les métriques précises d'Ollama."""
    print(f"\n---> Lancement du benchmark pour : {model_name}")

    if not check_model_available(model_name):
        print(f"[ATTENTION] Le modèle '{model_name}' n'est pas encore téléchargé dans Ollama.")
        return None

    prompt = (
        "Consigne : Rédige une synthèse concise et structurée en 5 points clés "
        "du texte suivant :\n\n" + TEXTE_TEST
    )

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 300,
        }
    }

    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            total_wall_time = time.time() - start_time
            data = json.loads(response.read().decode("utf-8"))

            # Métriques natives rapportées directement par Ollama
            total_duration_sec = data.get("total_duration", 0) / 1e9
            load_duration_sec = data.get("load_duration", 0) / 1e9
            prompt_eval_count = data.get("prompt_eval_count", 0)
            prompt_eval_sec = data.get("prompt_eval_duration", 0) / 1e9
            eval_count = data.get("eval_count", 0)
            eval_sec = data.get("eval_duration", 0) / 1e9

            tokens_per_second = (eval_count / eval_sec) if eval_sec > 0 else 0
            prompt_tokens_per_second = (prompt_eval_count / prompt_eval_sec) if prompt_eval_sec > 0 else 0

            return {
                "model": model_name,
                "total_wall_time_sec": round(total_wall_time, 2),
                "load_duration_sec": round(load_duration_sec, 2),
                "prompt_eval_count": prompt_eval_count,
                "prompt_tokens_per_second": round(prompt_tokens_per_second, 1),
                "eval_count": eval_count,
                "eval_duration_sec": round(eval_sec, 2),
                "tokens_per_second": round(tokens_per_second, 2),
                "response_preview": data.get("response", "")[:180].strip() + "..."
            }
    except urllib.error.URLError as e:
        print(f"[ERREUR] Échec de la communication avec Ollama : {e}")
        return None


def main() -> None:
    print("==========================================================")
    print("     BENCHMARK DES MODÈLES OLLAMA EN LOCAL (PC)          ")
    print("==========================================================")

    results = []
    for model in MODELS_TO_BENCH:
        res = bench_single_model(model)
        if res:
            results.append(res)

    if not results:
        print("\nAucun modèle parmi la liste cible n'a pu être exécuté.")
        print("Vérifie qu'Ollama est bien démarré (`ollama serve`).")
        print("\nCommandes pour télécharger les modèles nécessaires :")
        print("  ollama pull qwen2.5:7b      (pour le format 7B/8B)")
        print("  ollama pull qwen2.5:14b     (pour le format 14B)")
        return

    print("\n" + "=" * 70)
    print("                      RÉSULTATS COMPARATIFS                ")
    print("=" * 70)
    for r in results:
        print(f"\nModèle : {r['model']}")
        print(f"  - Vitesse de génération   : {r['tokens_per_second']} tokens/seconde")
        print(f"  - Ingestion du prompt     : {r['prompt_tokens_per_second']} tokens/seconde ({r['prompt_eval_count']} tokens)")
        print(f"  - Temps de chargement VRAM: {r['load_duration_sec']} s")
        print(f"  - Temps total d'exécution : {r['total_wall_time_sec']} s ({r['eval_count']} tokens générés)")
        print(f"  - Extrait de la réponse   : {r['response_preview']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
