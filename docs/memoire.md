# Conception de la Mémoire Multi-Agents

Le système multi-agents repose sur une architecture à double mémoire : une **mémoire court terme partagée** (spécifique à l'exécution d'une tâche) et une **mémoire long terme vectorielle** (persistante et transverse).

---

## 1. Mémoire Court Terme Partagée (Scratchpad d'Exécution)

### 1.1 Rôle et Cycle de Vie
La mémoire court terme est l'espace de travail collaboratif éphémère d'une tâche en cours :
- **Initialisation** : Instanciée dès la réception d'un objectif utilisateur par l'orchestrateur.
- **Accès partagé** : Chaque agent y lit le contexte global et y dépose ses résultats d'étape.
- **Fin de vie** : Persistée dans la base SQLite (`data/app.db`) et le journal JSONL à la clôture de la mission, puis libérée de la RAM.

### 1.2 Structure des Données Court Terme
La mémoire court terme contient :
1. **L'état d'avancement** : Objectif, statut global (`PENDING`, `RUNNING`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`), étape courante.
2. **Le plan d'action (`TaskPlan`)** : Liste des étapes avec statut individuel et sorties respectives.
3. **Le registre des faits certifiés (`list[Fact]`)** : Tous les faits validés extraits par le Lecteur et le Chercheur, consultables directement par l'Analyste, le Rédacteur et le Critique.
4. **Les artéfacts intermédiaires** : Scripts générés, tableaux bruts, graphiques temporaires.

---

## 2. Mémoire Long Terme Vectorielle (ChromaDB)

### 2.1 Rôle et Persistance
La mémoire long terme permet la recherche sémantique documentaire (RAG local) et la capitalisation des connaissances entre différentes sessions.
- **Moteur vectoriel** : ChromaDB en mode local persistant dans `data/chroma/`.
- **Modèle d'embedding** : `nomic-embed-text` servi localement par Ollama (`http://localhost:11434/api/embeddings`).
  - Dimension des vecteurs : 768.
  - Métrique de distance : Cosinus.
  - Préfixe de tâche recommandé : `search_document: ` pour l'indexation et `search_query: ` pour l'interrogation.

### 2.2 Stratégie de Découpage Documentaire (Chunking)
Pour garantir la traçabilité absolue de chaque extrait lors de l'analyse, le découpage suit des règles strictes :
1. **Unité de base : La page / section** :
   - Pour les PDF : extraction texte page par page via un parseur Python local.
   - Pour les DOCX / TXT : extraction par paragraphe ou section logique.
2. **Dimensionnement des morceaux (Chunks)** :
   - Taille nominale : **500 à 800 tokens** (environ 2 000 à 3 000 caractères).
   - Recouvrement (Overlap) : **100 tokens** pour préserver la continuité contextuelle entre deux morceaux consécutifs.
3. **Métadonnées obligatoires attachées à chaque chunk** :
   ```json
   {
     "source_file": "rapport_annuel_2025.pdf",
     "file_type": "pdf",
     "page_number": 14,
     "chunk_index": 3,
     "doc_id": "doc-hash-md5",
     "created_at": "2026-11-18T23:10:00"
   }
   ```

### 2.3 Mécanisme de Recherche et Récupération (Retrieval)
1. L'agent Lecteur soumet une question ou un ensemble de mots-clés.
2. Le texte de la requête est vectorisé via `nomic-embed-text` (`search_query: ...`).
3. ChromaDB renvoie les $k$ morceaux les plus proches sémantiquement (par défaut $k=5$).
4. Seuls les morceaux dont le score de similarité cosinus dépasse un seuil de confiance (ex. $\ge 0.65$) sont conservés et transformés en objets `Fact` traçables.

---

## 3. Modèle Commun de Faits (`Fact`)
Tout passage extrait de la mémoire (court terme ou long terme) est normalisé sous la forme d'un objet `Fact` :
- `assertion` : L'énoncé informatif synthétisé.
- `source_type` : `"document"` (local) ou `"web"`.
- `source_name` : Nom du fichier ou URL complète.
- `page_or_section` : Numéro de page (ex. `"Page 14"`) ou section.
- `exact_quote` : Citation textuelle exacte extraite du document d'origine.
- `confidence` : `"haute"`, `"moyenne"` ou `"faible"`.
