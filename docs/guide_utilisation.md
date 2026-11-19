# Guide d'utilisation

Assistant de recherche, de veille et d'analyse de documents qui tourne entièrement sur ton PC.

## 1. Installation (une seule fois)

1. Installer [Ollama](https://ollama.com/download), puis télécharger les modèles (≈ 15 Go) :

   ```powershell
   ollama pull qwen3:14b
   ollama pull qwen2.5-coder:7b
   ollama pull nomic-embed-text
   ```

2. Préparer Python (3.11 ou plus récent) dans le dossier du projet :

   ```powershell
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   copy .env.example .env
   ```

3. Vérifier l'environnement :

   ```powershell
   .venv\Scripts\python.exe scripts\check_env.py
   ```

   Chaque ligne doit afficher `[OK]`. Si un modèle manque, la commande `ollama pull` à lancer est indiquée.

> Si `qwen3:14b` n'est pas installé, le système bascule automatiquement sur le meilleur modèle présent
> (ex. `mistral`) : il fonctionne, mais les réponses sont moins fiables et plus lentes.

## 2. Démarrer

Double-clique sur `start.ps1` (ou `.\start.ps1` dans PowerShell). Le script vérifie Ollama, lance l'API
et l'interface dans deux fenêtres, puis ouvre le navigateur sur **http://localhost:8501**.

Pour arrêter : ferme les deux fenêtres « API multi-agents » et « Interface multi-agents ».

## 3. Utiliser l'interface

### Nouvelle tâche
1. Choisis le **type** : Synthèse de documents, Veille web, Comparatif, Question sur mes documents (ou Automatique).
2. Écris l'**objectif**, par exemple :
   - « Fais une synthèse de ces trois PDF avec les points clés. »
   - « Fais une veille sur l'IA dans la santé ce mois-ci. »
   - « Compare ces trois offres et recommande-m'en une. »
   - « Que dit ce contrat sur la résiliation ? »
3. Joins tes fichiers (PDF, Word, Excel, texte ; 20 Mo maximum chacun) et clique sur **Lancer**.

### Suivi
- Les étapes s'affichent en direct (plan, agent en cours, révisions du Critique).
- Si la validation humaine est activée, une demande **🔐 Validation requise** apparaît avant toute action
  risquée (recherche web, exécution de code) : clique sur **Autoriser** ou **Refuser**. Sans réponse en
  5 minutes, l'action est refusée.
- À la fin : le rapport s'affiche, avec ses sources numérotées ; télécharge-le en **Markdown** ou en **Word**.
- Donne ton avis 👍 / 👎 sur le rapport entier ou sur une section : il sert à améliorer les prompts.

### Comment lire un rapport
- Chaque affirmation renvoie à une source `[1]`, `[2]`… détaillée dans la table **Sources et Références**
  (fichier et page, ou URL, avec l'extrait exact).
- **⚠️ Rapport non validé par le Critique** en haut : un contrôle automatique a échoué (par exemple un
  chiffre qui n'apparaît dans aucune source). Vérifie avant d'utiliser le rapport.
- **ℹ️ Remarques du Critique (non bloquantes)** en bas : simples suggestions du modèle.
- **RAPPORT INCOMPLET** : une limite (temps, étapes, recherches web) a été atteinte ; le rapport contient ce
  qui avait été trouvé avant l'arrêt.

### Bibliothèque
Ajoute ici les documents que tu consultes souvent : ils sont indexés dans la mémoire long terme et les
agents peuvent les retrouver sans que tu les joignes à chaque tâche. « Retirer de l'index » ne supprime
jamais le fichier.

### Historique et Avis
L'historique liste toutes les tâches (y compris celles lancées en ligne de commande). La page Avis
résume les 👍 / 👎.

## 4. En ligne de commande

```powershell
# Une tâche complète
.venv\Scripts\python.exe main.py "Synthèse des points clés" --files C:\chemin\rapport.pdf

# Indexer le dossier data\documents dans la mémoire long terme
.venv\Scripts\python.exe scripts\index_docs.py

# Lire le journal détaillé d'une tâche
.venv\Scripts\python.exe scripts\show_log.py task-1234abcd

# Évaluer la qualité sur le jeu de 30 tâches (voir docs\rapport_qualite.md)
.venv\Scripts\python.exe scripts\evaluate.py
.venv\Scripts\python.exe scripts\evaluate.py --compare data\eval\<ancien>.json

# Transformer les avis 👎 en pistes d'amélioration
.venv\Scripts\python.exe scripts\feedback_report.py

# Veille programmée
.venv\Scripts\python.exe scripts\veille.py ajouter "IA locale et Ollama" --jours 7
.venv\Scripts\python.exe scripts\veille.py lancer
```

L'API est documentée sur **http://127.0.0.1:8000/docs** (formulaires pour tester chaque route).

## 5. Réglages (fichier `.env`)

| Réglage | Rôle | Valeur conseillée |
|---|---|---|
| `MODEL_PLANNER`, `MODEL_CODER`, `MODEL_EMBEDDING` | Modèles Ollama | `qwen3:14b`, `qwen2.5-coder:7b`, `nomic-embed-text` |
| `REQUIRE_HUMAN_APPROVAL` | Demander ton accord avant web et code | `true` pour plus de sécurité |
| `NUM_CTX` | Mémoire de travail du modèle (tokens) | `8192` (6 Go de VRAM) |
| `MAX_OUTPUT_TOKENS` | Longueur maximale d'une réponse | `2048` |
| `MAX_PARALLEL_STEPS` | Étapes indépendantes en parallèle | `2` (`1` si le PC sature) |
| `MAX_STEPS`, `MAX_SECONDS`, `MAX_WEB_SEARCHES`… | Limites par tâche | voir `.env.example` |
| `SEARXNG_URL` / `TAVILY_API_KEY` / `BRAVE_API_KEY` | Moteur de recherche web | SearXNG local (`docker compose up -d`) |
| `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` | Option Claude pour le planificateur et le critique | vide = 100 % local |

> **Option Claude** : avec une clé, l'objectif, les faits extraits et le rapport à vérifier sont envoyés à
> Anthropic. Les documents ne sont pas envoyés en entier, mais des extraits le sont. Laisse la clé vide pour
> que rien ne sorte de ton PC. En cas d'erreur Claude, le système repasse automatiquement sur Ollama.

## 6. Ajouter un agent

Crée un fichier `agents/definitions/<nom>.yaml` (exemple : `traducteur.yaml`) :

```yaml
name: comptable
role: Analyste comptable
model: planner        # planner, coder ou nom d'un modèle Ollama
tools: [read_document_pages, calculator]
prompt: |
  Tu es le comptable de l'équipe...
```

Il est chargé automatiquement ; le planificateur peut l'utiliser dès que son nom apparaît dans son prompt
(`agents/prompts/planner.md`).

## 7. Problèmes fréquents

| Problème | Solution |
|---|---|
| « L'API ne répond pas » dans l'interface | Relancer `start.ps1` ; vérifier la fenêtre « API multi-agents ». |
| « Ollama ne répond pas » | Ouvrir l'application Ollama (ou `ollama serve`). |
| Un modèle souhaité « n'est pas installé » | `ollama pull <nom>` puis relancer. |
| Tâches très lentes | Le modèle déborde de la carte graphique : passer `MODEL_PLANNER=qwen3:8b`, ou `NUM_CTX=6144`, ou `MAX_PARALLEL_STEPS=1`. |
| Recherche web vide | Lancer SearXNG (`docker compose up -d`) ou renseigner une clé Tavily/Brave. |
| PDF scanné « sans texte » | Le document est une image : il faut d'abord le passer dans un logiciel d'OCR. |
| Installation : erreur « Visual Studio » | Utiliser `requirements.txt` à jour (chromadb 1.x a des paquets précompilés). |
