# Tests & évaluation

Trois zones distinctes, par **nature** de ce qui est vérifié :

| Dossier | Quoi | Déterministe ? | Lancer |
|---|---|---|---|
| **`unit/`** | Tests unitaires des parties **déterministes** de l'agent : calcul des métriques, outils, sélection, résilience réseau. Rapides, **sans réseau** — c'est ce que joue la CI. | ✅ | `pytest tests/unit` |
| **`agent_eval/`** | Évaluation **bout-en-bout de l'agent** : exerce toute la boîte à outils et mesure la **couverture d'outils**, la latence et les tokens. Nécessite une clé API. | ❌ (LLM) | `python tests/agent_eval/run_golden.py` |
| **`rag_eval/`** | Évaluation de la **récupération du moteur** RAG (recall@k, MRR, citations, RAGAS). Nécessite les modèles + données du moteur. | ❌ (RAG) | `python -m tests.rag_eval.run --config tests/rag_eval/configs/eval_finance.yaml` |

> Pourquoi séparer : les tests **unitaires** doivent rester rapides et verts en CI ;
> les **évals** (agent et moteur) sont coûteuses (LLM, modèles) et produisent des
> rapports à analyser, pas des assertions pass/fail sur une chaîne exacte.

## `unit/` — pytest

```bash
pytest tests/unit                 # tout
pytest tests/unit/agent_finance   # uniquement les métriques rating fond
```

## `agent_eval/` — éval de l'agent

`question_test.yaml` (20 questions, 9 catégories, chacune taguée `expected_tools`)
exerce **toute la boîte à outils**. `run_golden.py` écrit un rapport dans
`agent_eval/reports/`, auto-étiqueté par modèle.

```bash
python tests/agent_eval/run_golden.py                                          # modèle par défaut (Opus)
RAG__LLM__OPENAI__MODEL=claude-haiku-4-5 python tests/agent_eval/run_golden.py  # ablation Haiku
python tests/agent_eval/run_golden.py question_test.yaml 3                      # 3 premières questions
```

Le rapport mesure, par question : **couverture d'outils** (`expected_tools ⊆` outils
appelés), latence, tokens ; agrégés par catégorie + matrice des outils exercés.
`golden_fonds_v1.yaml` est l'ancien jeu générique (lookups RAG seuls), conservé pour référence.

## `rag_eval/` — éval de la récupération

Package autonome (imports relatifs). Configs dans `rag_eval/configs/`, golden sets dans
`rag_eval/golden/` (un par dataset, jamais combinés).

```bash
python -m tests.rag_eval.run     --config tests/rag_eval/configs/eval_droit.yaml          # corpus droit
python -m tests.rag_eval.run     --config tests/rag_eval/configs/eval_finance.yaml  # corpus finance
python -m tests.rag_eval.compare --config tests/rag_eval/configs/eval_finance.yaml  # dense / hybrid / +reranker
```
