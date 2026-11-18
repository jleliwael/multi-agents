# Référentiel des Agents Spécialistes

Ce document formalise les fiches d'identité des 7 agents du système multi-agents local. Chaque agent possède un périmètre strict, un modèle LLM assigné, un sous-ensemble d'outils autorisés et des contrats d'entrée/sortie précis.

---

## 1. Planificateur (Planner)
- **Rôle** : Reçoit l'objectif global de l'utilisateur, analyse la faisabilité, et génère un graphe d'étapes séquentielles ou parallélisables avec leurs dépendances strictes.
- **Modèle Ollama** : `qwen3:14b` (température basse: 0.1 pour un raisonnement rigoureux).
- **Outils autorisés** :
  - `datetime_tool` (date et heure courante pour ancrer les requêtes temporelles).
- **Format d'entrée** : Objectif utilisateur (`str`), liste des fichiers fournis en entrée (`list[str]`), contraintes de temps et de sortie.
- **Format de sortie** : `TaskPlan` (JSON strict validé par Pydantic) contenant la liste ordonnée des étapes (`steps`), les dépendances et l'agent assigné à chaque étape.

---

## 2. Chercheur Web (Researcher)
- **Rôle** : Effectue la prospection documentaire externe sur le Web pour la veille, les benchmarks et les faits récents. Soumis au contrôle de sécurité.
- **Modèle Ollama** : `qwen3:14b` (température: 0.2).
- **Outils autorisés** :
  - `web_search` (moteur de recherche web en lecture seule GET).
  - `datetime_tool` (calibrage des requêtes temporelles).
- **Format d'entrée** : Requête de recherche textuelle, plage de dates, nombre maximum de sources.
- **Format de sortie** : Liste d'objets `Fact` (avec URL exacte, extrait textuel brut, affirmation et niveau de confiance) et résumé préliminaire des sources trouvées.

---

## 3. Lecteur de Documents et Mémoire (Reader)
- **Rôle** : Spécialiste de l'ingestion documentaire locale (PDF, DOCX, TXT, CSV) et de l'interrogation de la base vectorielle ChromaDB (RAG local).
- **Modèle Ollama** : `qwen3:14b` (température: 0.1).
- **Outils autorisés** :
  - `documents` (parseurs PDF, DOCX, TXT, extraction page par page).
  - `memory_search` (recherche sémantique de passages similaires dans ChromaDB).
  - `files` (lecture de fichiers dans `data/workspace/` et `data/uploads/`).
- **Format d'entrée** : Liste des fichiers cibles ou question documentaire ciblée.
- **Format de sortie** : Liste d'objets `Fact` (avec métadonnées obligatoires : nom de fichier, numéro de page, paragraphe, extrait exact) et synthèse des passages pertinents.

---

## 4. Analyste (Analyst)
- **Rôle** : Croise les faits extraits par le Chercheur et le Lecteur. Détecte les contradictions entre sources, évalue la solidité des preuves et construit les matrices de comparaison.
- **Modèle Ollama** : `qwen3:14b` (température: 0.2).
- **Outils autorisés** :
  - `calculator` (calculs arithmétiques basiques).
- **Format d'entrée** : Liste consolidée des `Fact` (provenant du Lecteur et/ou du Chercheur), critères d'évaluation ou grille de comparaison.
- **Format de sortie** : `AnalysisResult` contenant :
  - Matrice des points communs et divergences.
  - Identification des contradictions éventuelles avec citations des deux sources opposées.
  - Synthèse analytique consolidée.

---

## 5. Codeur (Coder)
- **Rôle** : Rédige des scripts Python exécutés dans le bac à sable local (`data/sandbox/`) pour des calculs statistiques précis, le traitement de fichiers tabulaires (Excel/CSV) et la génération de graphiques légers (PNG/SVG).
- **Modèle Ollama** : `qwen2.5-coder:7b` (modèle spécialisé en code, température: 0.1).
- **Outils autorisés** :
  - `code_runner` (exécution sécurisée de code Python en subprocess isolé dans `data/sandbox/` avec timeout de 15s).
  - `files` (lecture/écriture restreinte au dossier `data/sandbox/`).
- **Format d'entrée** : Consigne de calcul/génération, description des données sources, format du résultat attendu.
- **Format de sortie** : Code Python produit, code de retour (stdout / stderr), valeurs calculées exactes et chemin des graphiques générés.

---

## 6. Rédacteur (Writer)
- **Rôle** : Rédige le livrable final en Markdown professionnel à partir des analyses consolidées, des faits sourcés et des templates prédéfinis.
- **Modèle Ollama** : `qwen3:14b` (température: 0.3 pour un style rédactionnel fluide mais rigoureux).
- **Outils autorisés** :
  - `files` (écriture du livrable dans `data/reports/`).
- **Format d'entrée** : Template choisi (`synthese.md`, `veille.md` ou `comparatif.md`), faits certifiés (`list[Fact]`), analyse de l'Analyste, graphiques du Codeur.
- **Format de sortie** : Document Markdown final complet, intégrant la bibliographie annotée et toutes les citations rattachées aux sources.

---

## 7. Critique (Critic)
- **Rôle** : Agent d'assurance qualité. Relit le rapport du Rédacteur, vérifie que chaque affirmation correspond bien à un `Fact` tracé, vérifie l'absence d'hallucinations et juge si les critères du cahier des charges sont remplis.
- **Modèle Ollama** : `qwen3:14b` (température: 0.1).
- **Outils autorisés** :
  - Aucun outil d'exécution (analyse critique pure du texte produit face aux faits sources).
- **Format d'entrée** : Rapport final produit, liste des `Fact` d'origine, critères de succès de la tâche.
- **Format de sortie** : `CriticEvaluation` :
  - `is_approved` : booléen (`True` si validé, `False` si révision requise).
  - `score_qualite` : note sur 10.
  - `anomalies` : liste des écarts constatés (affirmation sans source, chiffre inexact, section manquante).
  - `recommandations` : consignes d'amélioration précises pour la passe de révision (dans la limite de 2 révisions max).
