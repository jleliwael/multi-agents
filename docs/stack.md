# Choix Techniques et Pile Technologique (Stack)

Ce document formalise les choix d'outils, les bibliothèques retenues, leurs versions et la justification architecturale pour le système multi-agents local.

---

## 1. Justification des Choix Structurants

### 1.1 Code Maison vs Frameworks (LangChain, CrewAI, LangGraph)
- **Maîtrise totale du flux d'exécution** : Les frameworks de haut niveau introduisent des abstractions lourdes, des surcoûts de tokens dans les invites cachées et des dépendances fragiles.
- **Transparence et Débogage** : Le code maison permet de tracer chaque requête HTTP brute vers l'API Ollama locale, de contrôler le JSON généré sans parseur magique et d'éviter les boucles infinies imprévues.
- **Performance locale** : Aucune surcharge CPU/RAM superflue sur une machine aux ressources calibrées (32 Go RAM, 6 Go VRAM).

### 1.2 SQLite pour l'Historique des Tâches
- **Simplicité opérationnelle** : Un simple fichier de base de données local (`data/app.db`) sans serveur de bases de données externe à installer ou maintenir en tâche de fond.
- **Concurrence et ACID** : Parfaitement adapté au mode WAL (Write-Ahead Logging) pour enregistrer simultanément les statuts d'étapes et les retours utilisateurs.
- **Évolution future** : Séparation stricte via `storage/repository.py` permettant une transition transparente vers PostgreSQL ultérieurement.

### 1.3 ChromaDB pour la Mémoire Vectorielle (RAG Local)
- **Mode embarqué persistant** : S'exécute directement dans le processus Python (`PersistentClient(path="data/chroma")`), sans nécessiter de conteneur Docker distinct.
- **Compatibilité native** : Gestion transparente des embeddings de dimension 768 fournis par `nomic-embed-text`.
- **Faible empreinte mémoire** : Moins de 300 Mo de RAM consommée au repos.

---

## 2. Bibliothèques de Traitement Documentaire Retenues

### 2.1 PDF : `PyMuPDF` (`fitz`) — Version 1.25.x
- **Pourquoi PyMuPDF et non pypdf ?**
  - **Vitesse d'extraction** : PyMuPDF est 10 à 25 fois plus rapide que les bibliothèques pur Python sur les fichiers de 50 à 200 pages.
  - **Fidélité de mise en page** : Restitution précise de l'ordre de lecture des colonnes et des blocs de texte.
  - **Découpage page par page exact** : Garantit le rattachement formel du numéro de page à chaque objet `Fact`.

### 2.2 Word : `python-docx` — Version 1.1.x
- Standard de référence pour l'inspection des paragraphes, des styles de titres hiérarchiques et des tableaux dans les fichiers `.docx`.

### 2.3 Excel : `openpyxl` — Version 3.1.x
- Permet la lecture cellule par cellule, l'inspection des onglets et l'extraction brute des feuilles de calcul sans lancer d'instance Excel en arrière-plan.

### 2.4 Extraction Web : `trafilatura` — Version 2.0.x
- **Pourquoi trafilatura ?**
  - Nettoyage expert du bruit HTML : Élimine automatiquement les menus de navigation, bannières de cookies, pieds de page et publicités.
  - Restitution en texte brut propre ou en Markdown direct prêt à être digéré par le modèle LLM.

---

## 3. Tableau Récapitulatif des Versions Fixées

| Composant / Bibliothèque | Version Fixée | Rôle / Justification |
| :--- | :--- | :--- |
| **Python** | `3.13.x` | Environnement d'exécution système |
| **Ollama** | `0.40.x` | Moteur d'inférence LLM local |
| **httpx** | `0.28.1` | Client HTTP asynchrone pour l'API Ollama |
| **pydantic** | `2.10.4` | Validation des schémas d'entrée/sortie (`Fact`, `TaskPlan`) |
| **python-dotenv** | `1.0.1` | Chargement du `.env` |
| **fastapi** | `0.115.6` | API REST backend pour l'orchestration |
| **uvicorn** | `0.34.0` | Serveur ASGI haute performance |
| **streamlit** | `1.42.0` | Interface utilisateur interactive locale |
| **chromadb** | `0.6.3` | Moteur vectoriel persistant local |
| **pymupdf** | `1.25.3` | Extraction textuelle ultra-rapide des PDF |
| **python-docx** | `1.1.2` | Extraction documentaire Word (.docx) |
| **openpyxl** | `3.1.5` | Lecture et traitement des classeurs Excel |
| **trafilatura** | `2.0.0` | Scraping web propre et dépouillé |
