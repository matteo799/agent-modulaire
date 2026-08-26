# Tests & évaluation

Trois zones distinctes, par **nature** de ce qui est vérifié :

| Dossier | Quoi | Déterministe ? | Lancer |
|---|---|---|---|
| **`unit/`** | Tests unitaires des parties **déterministes** de l'agent : calcul des métriques, outils, sélection, résilience réseau. Rapides, **sans réseau** — c'est ce que joue la CI. | ✓ | `pytest tests/unit` |
| **`agent_eval/`** | Évaluation **bout-en-bout de l'agent** : exerce toute la boîte à outils et mesure la **couverture d'outils**, la latence et les tokens. Nécessite une clé API. | ✗ (LLM) | `python tests/agent_eval/run_golden.py` |
| **`rag_eval/`** | Évaluation de la **récupération du moteur** RAG (recall@k, MRR, citations, RAGAS). Nécessite les modèles + données du moteur. **Aucun rapport n'est versionné** — le harness existe, ses résultats ne sont donc pas revendiqués. | ✗ (RAG) | `python -m tests.rag_eval.run --config tests/rag_eval/configs/eval_finance.yaml` |

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

> Les deux rapports actuellement versionnés couvrent **19 des 20 questions** : la question
> de catégorie `multi-etapes` n'a pas été rejouée dans la dernière passe. Les scores
> annoncés (14/15 Opus, 12/15 Haiku) portent donc sur ces 19 questions.

```bash
python tests/agent_eval/run_golden.py                                          # modèle par défaut (Opus)
RAG__LLM__OPENAI__MODEL=claude-haiku-4-5 python tests/agent_eval/run_golden.py  # ablation Haiku
python tests/agent_eval/run_golden.py question_test.yaml 3                      # 3 premières questions
```

Le rapport mesure, par question : **couverture d'outils** (`expected_tools ⊆` outils
appelés), latence, tokens ; agrégés par catégorie + matrice des outils exercés. La
**justesse de la réponse n'est pas scorée automatiquement** — `expected_answer` est un
critère de lecture, pas une chaîne exacte.

`golden_fonds_v1.yaml` est l'ancien jeu générique (lookups RAG seuls), conservé pour
référence. `demo_gerant.yaml` est le jeu long (40 questions de gérant, dataset Amundi).

**Interprétation des résultats — ce qu'ils montrent et ce qu'ils ne montrent pas :**
[`../docs/benchmarks.md`](../docs/benchmarks.md).

### Justesse des réponses — `score_accuracy.py`

La couverture d'outils mesure la **conformité de trajectoire**, pas la valeur livrée : un
agent peut appeler les bons outils et énoncer un chiffre faux. Ce script mesure l'autre axe.

```bash
python tests/agent_eval/score_accuracy.py                 # rapport gérant par défaut
python tests/agent_eval/score_accuracy.py chemin/rapport.md
```

Il n'appelle **aucun LLM** : le dataset Amundi étant structuré et historisé, la bonne réponse
est recalculée avec `agent/finance/` — le même code que les outils — puis comparée au texte
du rapport déjà versionné. La justesse se mesure donc **a posteriori, sans accès API**.

Dernière passe (run gérant, Opus 4.8) : **45/46 assertions vérifiées sur 27 des 40
questions**, contre **26 % pour le témoin négatif** (chaque question notée avec la réponse
d'une autre). Ce témoin tourne à chaque exécution : s'il ne s'effondre pas, le barème valide
du bruit. Résultat versionné dans `reports/accuracy_demo_gerant_claude-opus-4-8.md`.

Les 13 questions non mécanisables (screening, adéquation, audit) sont nommées dans le script
et comptées à part, jamais omises silencieusement.

### Ablation architecturale — `run_ablation.py`

Fait passer les mêmes questions par cinq architectures pour isoler l'apport de chaque
composant : `A` récupération seule, `B` + outillage, `C` + planification, `D` + boucle de
correction (config de production), `E` avec un juge LLM à la place de la règle déterministe.

```bash
python tests/agent_eval/run_ablation.py --arms A,B,C,D,E
python tests/agent_eval/run_ablation.py --arms A,D --limit 3   # passe courte
```

La notation est **entièrement déterministe** — aucun juge LLM — : couverture d'outils, refus
correct sur les questions hors-corpus, et un proxy d'ancrage numérique (tout nombre de la
réponse doit se retrouver dans un résultat d'outil ou dans la question).

**Ce harness n'a jamais été exécuté** faute d'accès API. Il est couvert par
`tests/unit/agent/test_ablation_harness.py`, qui vérifie contre un LLM factice que les cinq
bras s'exécutent, que `C` ne retente jamais une étape là où `D` la retente une fois, et que
les métriques se comportent comme annoncé. Aucun résultat par composant n'est revendiqué.

## `rag_eval/` — éval de la récupération

Package autonome (imports relatifs). Configs dans `rag_eval/configs/`, golden sets dans
`rag_eval/golden/` (un par dataset, jamais combinés).

```bash
python -m tests.rag_eval.run     --config tests/rag_eval/configs/eval_droit.yaml          # corpus droit
python -m tests.rag_eval.run     --config tests/rag_eval/configs/eval_finance.yaml  # corpus finance
python -m tests.rag_eval.compare --config tests/rag_eval/configs/eval_finance.yaml  # dense / hybrid / +reranker
```
