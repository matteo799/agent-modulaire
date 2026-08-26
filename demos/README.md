# Démos

Chaque fichier est la sortie réelle d'un run, versionnée telle quelle. Rien n'a été retouché
à la main, y compris quand le système refuse de répondre.

Pour voir l'agent complet à l'œuvre, commencer par `demo_Amundi.md`. Pour la seule démo qui
compare deux configurations, `demo_comparaison.md`.

| Démo | Ce qu'elle montre | Résultat |
|---|---|---|
| `demo_Amundi.md` | l'agent autonome sur 40 questions d'un gérant, dataset Amundi (474 fonds). Trajectoire complète par question : plan, outil choisi, raison du choix, résultat. | 31/33 de couverture d'outils, 23 outils sur 28 exercés |
| `demo_multi_tache.md` | 5 tâches multi-étapes, celles qu'un RAG seul ne peut pas exprimer : enchaîner plusieurs recherches, calculer, produire un livrable. | 5/5 menées à terme |
| `demo_30_questions.md` | le RAG seul (récupération, reranker, génération ancrée) sur 30 questions finance. Sert de référence basse. | 19/30 répondues, 3/3 pièges refusés |
| `demo_30_questionsCRAG.md` | le même corpus en mode CRAG : juge chaque passage, réécrit la requête si insuffisant. | 19/30 répondues, 3/3 pièges refusés |
| `demo_comparaison.md` | les deux précédentes côte à côte, question par question. | égalité, 8 divergences |

## Le résultat qui compte

`demo_comparaison.md` est une ablation dont le résultat est négatif. La boucle corrective
CRAG coûte une passe LLM de plus par requête et n'améliore pas le taux de réponse : 19/30
dans les deux modes. Elle modifie 8 réponses, mais les gains et les pertes s'annulent. Elle
récupère Q2 et Q4, et perd Q6, une question que le mode rapide traitait correctement avec
citation, adresse postale et procédure de réclamation.

C'est la raison pour laquelle CRAG est resté une option et n'est pas devenu le défaut.

Les deux modes refusent les 3 pièges hors-corpus, donc la garantie d'ancrage ne dépend pas
de la boucle corrective.

L'analyse complète est dans [`../docs/benchmarks.md`](../docs/benchmarks.md).

## Différence avec `tests/agent_eval/reports/`

Ces démos sont des sorties lisibles de bout en bout. Les rapports d'évaluation sont générés
par `run_golden.py` et portent les mesures automatiques : couverture d'outils, latence,
tokens, agrégats par catégorie.

`demo_Amundi.md` et `reports/golden_report_demo_gerant_claude-opus-4-8.md` viennent du même
run, `demo-gerant-v1.2`. La démo en est la version lisible, le rapport la version mesurée.
