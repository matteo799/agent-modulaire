# Rapport golden — demo_gerant.yaml

Version : `demo-gerant-v1.2` — 1 question(s) — temps total : 96s

## Comment lire ce rapport

Pour chaque question, l'agent travaille **en autonomie** en 3 temps :
1. **il comprend l'intention** (et, pour une métrique, choisit laquelle — ou demande une clarification si c'est ambigu) ;
2. **il établit un plan** puis, étape par étape, **choisit l'outil adapté** (la *raison* de chaque choix est affichée) et l'exécute ;
3. **il rédige la réponse finale** à partir des résultats.

Le bloc « 🧭 Comment l'agent a procédé » montre cette trajectoire ; « ✅ Réponse de l'agent » donne le livrable. Les chiffres sont **calculés sur les vraies données** (historique NAV, fiches structurées) — jamais inventés.

**Couverture d'outils globale : 0/0 questions** (les outils attendus ont bien été appelés).

**Outils exercés : 2/28** — rag_search, write_file  ·  _manquants :_ list_documents, count_funds, find_fund, invested_value, compare_funds, fund_calendar, fund_period, fund_monthly, fund_underwater, fund_rolling_sharpe, funds_correlation, fund_tail_risk, fund_nav_series, fees_projection, fund_summary, fund_stats, fund_performance, screen_funds, read_file, calculator, metric_sharpe, metric_sortino, metric_starr, metric_martin, metric_rdt_max_cvar, metric_rdt_max_drawdown

## Synthèse par catégorie

| Catégorie | Q | Couverture outils | Latence moy. | Tokens moy. |
|---|---|---|---|---|
| hors-perimetre | 1 | — | 96.2s | ~15479 |

> La justesse de la réponse reste à valider à l'œil (le critère « réponse attendue » n'est pas une chaîne exacte). La **couverture d'outils**, la **latence** et les **tokens** sont mesurés automatiquement. Coût en tokens = estimation (count_tokens du client), pour comparer, pas pour facturer.

---

## g38-composition-holdings  ·  `hors-perimetre`

**Question :** Quelles sont les 10 principales positions (titres en portefeuille) du fonds FR0011223569 et sa répartition sectorielle ?

**Outils appelés :** ['rag_search', 'write_file']  ·  **couverture :** —  ·  **latence :** 96.2s  ·  **tokens :** ~15479

### 🧭 Comment l'agent a procédé (en autonomie)

- **Plan :** Rechercher les 10 principales positions (titres en portefeuille) du fonds FR0011223569… → Rechercher la répartition sectorielle du fonds FR0011223569 via rag_search → Synthétiser les informations collectées et écrire le rapport final avec write_file
- **Étape 1 → `rag_search`** : L'étape demande explicitement de rechercher les 10 principales positions du fonds FR0011223569 via rag_search. Bien que les positions en portefeuille soient des données structurées, l'étape prescrit…
    ↳ _résultat :_ Aucun passage pertinent trouvé dans les documents pour cette recherche : le sujet ne semble pas couvert par les documents disponibles.
- **Étape 2 → `rag_search`** : La répartition sectorielle est une information qualitative, décrite en texte libre dans les documents du fonds (fiche descriptive, prospectus, factsheet). rag_search est conçu pour chercher ce type…
    ↳ _résultat :_ Aucun passage pertinent trouvé dans les documents pour cette recherche : le sujet ne semble pas couvert par les documents disponibles.
- **Étape 3 → `write_file`** : L'étape demande explicitement d'écrire le rapport final avec write_file. Les recherches précédentes n'ont trouvé aucune donnée sur les positions ni la répartition sectorielle du fonds FR0011223569.…
    ↳ _résultat :_ Fichier écrit : workspace/rapport_FR0011223569.md (1086 caractères)

### ✅ Réponse de l'agent

Les documents fournis ne permettent pas de répondre à cette question.

---
