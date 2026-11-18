# Cahier des Charges — Système Multi-Agents Local

## 1. Vision et Objectifs
Le système est une plateforme d'orchestration multi-agents autonome, privée et opérant **100 % en local** sur PC. 
Son domaine principal est **la recherche, la veille et l'analyse de documents**.
À partir d'un objectif utilisateur en langage naturel (ex. analyser des rapports, faire une veille web ou comparer des solutions), une équipe d'agents coordonnés exécute la mission de bout en bout et livre un rapport structuré en Markdown.

---

## 2. Rôles et Équipe d'Agents
1. **Planificateur (`qwen3:14b`)** : Décompose l'objectif en un graphe d'étapes ordonnées avec dépendances en format JSON strict.
2. **Chercheur** : Extrait et indexe les documents locaux (PDF, DOCX, TXT) et mène la recherche d'informations (locale / web contrôlé).
3. **Analyste** : Traite les données quantitatives et qualitatives, structure les matrices comparatives et synthétise les points clés.
4. **Codeur (`qwen2.5-coder:7b`)** : Rédige et exécute des scripts Python dans un bac à sable isolé pour extraire, parser ou calculer.
5. **Rédacteur** : Rédige le livrable final en Markdown professionnel avec plans, tableaux et citations de sources.
6. **Critique** : Évalue la conformité du livrable par rapport aux critères initiaux et déclenche jusqu'à 2 révisions si nécessaire.

---

## 3. Critères de Réussite Mesurables
- **Qualité des livrables** : Taux d'exactitude factuelle $\ge 95\ \%$, respect du format Markdown demandé, présence obligatoire des sources/extraits cités, zéro hallucination sur les chiffres.
- **Temps d'exécution (adapté RTX 3050 Laptop - 6 Go VRAM)** :
  - Tâche simple (synthèse mono-document) : $\le 2$ minutes.
  - Tâche intermédiaire (analyse multi-documents ou veille web) : $\le 5$ minutes.
  - Tâche complexe (benchmark comparatif multi-sources avec code) : $\le 10$ minutes.
- **Coût d'exploitation** : **0,00 €** (exécution 100 % locale via Ollama, sans API payante externe).

---

## 4. Politique de Sécurité et Interdits Absolus (Gardefous)
Toute action sensible est soumise à la validation humaine explicite (*Human-in-the-Loop*) via l'interface :
1. **Zéro écriture hors périmètre** : Interdiction absolue d'écrire ou de modifier des fichiers en dehors de `data/workspace/` et `data/sandbox/`.
2. **Zéro suppression destructrice** : Interdiction formelle de supprimer des fichiers ou des répertoires sans approbation explicite.
3. **Zéro transaction financière** : Aucune interaction avec des passerelles de paiement ou d'achat.
4. **Zéro communication externe non sollicitée** : Aucun envoi d'e-mail, de message, de webhook ou d'upload de données privées vers l'extérieur.
5. **Recherche Web régulée** : Les requêtes HTTP sortantes sont limitées à la consultation documentaire (GET) et désactivables en mode hors-ligne.

---

## 5. Environnement et Architecture Cible
- **Modèles LLM** : `qwen3:14b` (cerveau/plan), `qwen2.5-coder:7b` (code/sandbox), `nomic-embed-text` (embeddings vectoriels).
- **Stockage & Mémoire** : SQLite (`data/app.db`) pour l'historique et les statuts, ChromaDB (`data/chroma/`) pour la mémoire vectorielle long terme, mémoire court terme partagée en RAM.
- **Interfaces** : Backend API FastAPI asynchrone, Frontend Streamlit réactif avec suivi en direct et validation humaine.
