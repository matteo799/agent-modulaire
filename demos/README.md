# Démos — sorties rejouables

Chaque fichier est la **sortie réelle** d'un run, versionnée telle quelle. Rien n'est
retouché à la main : c'est ce que le système a produit, y compris quand il refuse de
répondre.

**Par où commencer :** `demo_Amundi.md` pour voir l'agent complet à l'œuvre,
`demo_comparaison.md` pour la seule démo qui compare deux configurations.

| Démo | Ce qu'elle montre | Résultat | Taille |
|---|---|---|---|
| **`demo_Amundi.md`** | **Démo phare.** L'agent autonome sur 40 questions d'un gérant, dataset Amundi (474 fonds). Trajectoire complète par question : plan, outil choisi, raison du choix, résultat. | 31/33 couverture d'outils · 23/28 outils exercés | 1 954 l. |
| `demo_multi_tache.md` | 5 tâches **multi-étapes** — celles qu'un RAG seul ne peut pas exprimer : enchaîner plusieurs recherches, calculer, produire un livrable. | 5/5 menées à terme | 207 l. |
| `demo_30_questions.md` | Le **RAG seul** (récupération → reranker → génération ancrée) sur 30 questions finance. Sert de référence basse. | 19/30 répondues · 3/3 pièges refusés | 133 l. |
| `demo_30_questionsCRAG.md` | Le **même corpus en mode CRAG** (juge chaque passage, réécrit la requête si insuffisant). | 19/30 répondues · 3/3 pièges refusés | 157 l. |
| `demo_comparaison.md` | **Les deux précédentes côte à côte**, question par question. | Égalité · 8 divergences | 134 l. |

## Le résultat qui compte

`demo_comparaison.md` est une **ablation avec résultat négatif** : la boucle corrective
CRAG coûte une passe LLM supplémentaire par requête et n'améliore pas le taux de réponse
(19/30 dans les deux modes). Elle modifie 8 réponses, mais les gains et les pertes
s'annulent — elle récupère des réponses (Q2, Q4) et en **perd** d'autres qu'elle
répondait correctement auparavant (Q6). C'est la raison pour laquelle CRAG est resté une
option et n'est pas devenu le défaut.

Les deux modes refusent 3/3 des pièges hors-corpus : la garantie d'ancrage ne dépend pas
de la boucle corrective.

Analyse complète et mise en perspective : [`../docs/benchmarks.md`](../docs/benchmarks.md).

## À ne pas confondre avec `tests/agent_eval/reports/`

Ces démos sont des **sorties de démonstration**, lisibles de bout en bout. Les rapports
d'évaluation, eux, sont générés par le harness `run_golden.py` et portent les **mesures
automatiques** (couverture d'outils, latence, tokens, agrégats par catégorie).
`demo_Amundi.md` et `reports/golden_report_demo_gerant_claude-opus-4-8.md` proviennent du
même run (`demo-gerant-v1.2`) : la démo est la version lisible, le rapport la version
mesurée.
