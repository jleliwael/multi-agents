# Rapport qualité — évaluation chiffrée

- **Date :** 2026-11-20 02:01 UTC
- **Modèle :** qwen3:14b
- **Mode :** réel
- **Fichier de résultats :** `data/eval/20261120_030131.json`

## Résultat global

| Tâches | Réussite | Score moyen | Temps moyen | Citations inventées | Note du juge |
|---|---|---|---|---|---|
| 10 | 90.0 % | 94.0/100 | 733.4 s | 0 | — |

## Par famille de tâche

| Famille | Tâches | Réussite | Score moyen | Temps moyen |
|---|---|---|---|---|
| comparatif | 2 | 100.0 % | 95.0/100 | 719.3 s |
| donnees | 2 | 100.0 % | 90.0/100 | 1284.5 s |
| question | 3 | 100.0 % | 100.0/100 | 277.7 s |
| robustesse | 1 | 100.0 % | 90.0/100 | 642.5 s |
| synthese | 1 | 0.0 % | 90.0/100 | 615.4 s |
| traduction | 1 | 100.0 % | 90.0/100 | 1235.3 s |

## Erreurs les plus fréquentes

- Temps maximum dépassé : 6 tâche(s)
- Mission non terminée (INCOMPLET) : 1 tâche(s)

## Détail par tâche

| Tâche | Famille | Statut | Score | Durée | Problèmes |
|---|---|---|---|---|---|
| eval-01 Chiffre d'affaires 2025 | question | ✅ COMPLETED | 100.0 | 246.6 s | — |
| eval-07 Objectif 2026 | question | ✅ COMPLETED | 100.0 | 228.5 s | — |
| eval-11 Opérations soumises à approbation | question | ✅ COMPLETED | 100.0 | 358.0 s | — |
| eval-13 Chiffre d'affaires du trimestre | donnees | ✅ COMPLETED | 90.0 | 758.3 s | — |
| eval-15 Marge nette moyenne | donnees | ✅ COMPLETED | 90.0 | 1810.7 s | — |
| eval-17 Synthèse du rapport annuel | synthese | ❌ INCOMPLET | 90.0 | 615.4 s | [Action : vague_3] Temps maximum dépassé (615.4s / 600s). |
| eval-22 Comparer trois offres | comparatif | ✅ COMPLETED | 90.0 | 933.1 s | — |
| eval-24 Offre la moins chère | comparatif | ✅ COMPLETED | 100.0 | 505.5 s | — |
| eval-26 Traduire un rapport anglais | traduction | ✅ COMPLETED | 90.0 | 1235.3 s | — |
| eval-28 Information absente (effectif) | robustesse | ✅ COMPLETED | 90.0 | 642.5 s | — |

> Généré par `python scripts/evaluate.py`. Méthode de notation : voir l'en-tête du script.
