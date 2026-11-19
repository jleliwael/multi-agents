# Rapport qualité — évaluation chiffrée

- **Date :** 2026-11-19 18:29 UTC
- **Modèle :** mistral:latest
- **Mode :** réel
- **Fichier de résultats :** `data/eval/20261119_192951.json`

## Résultat global

| Tâches | Réussite | Score moyen | Temps moyen | Citations inventées | Note du juge |
|---|---|---|---|---|---|
| 5 | 80.0 % | 82.0/100 | 372.4 s | 0 | — |

## Par famille de tâche

| Famille | Tâches | Réussite | Score moyen | Temps moyen |
|---|---|---|---|---|
| comparatif | 1 | 100.0 % | 70.0/100 | 611.5 s |
| donnees | 1 | 100.0 % | 100.0/100 | 308.5 s |
| question | 2 | 100.0 % | 100.0/100 | 330.7 s |
| robustesse | 1 | 0.0 % | 40.0/100 | 280.5 s |

## Erreurs les plus fréquentes

- Sources insuffisantes ou document non cité : 1 tâche(s)
- Temps maximum dépassé : 1 tâche(s)
- Éléments attendus absents du rapport : 1 tâche(s)

## Détail par tâche

| Tâche | Famille | Statut | Score | Durée | Problèmes |
|---|---|---|---|---|---|
| eval-01 Chiffre d'affaires 2025 | question | ✅ COMPLETED | 100.0 | 489.0 s | — |
| eval-10 Décision sur l'exécution locale | question | ✅ COMPLETED | 100.0 | 172.4 s | — |
| eval-13 Chiffre d'affaires du trimestre | donnees | ✅ COMPLETED | 100.0 | 308.5 s | — |
| eval-22 Comparer trois offres | comparatif | ✅ COMPLETED | 70.0 | 611.5 s | — |
| eval-28 Information absente (effectif) | robustesse | ❌ COMPLETED | 40.0 | 280.5 s | manque : ne mentionne pas / ne precise pas / n'indique pas / pas d'information / aucune information / non mentionne / non precise / introuvable / ne contient pas / pas mentionne / pas precise / pas indique |

> Généré par `python scripts/evaluate.py`. Méthode de notation : voir l'en-tête du script.
