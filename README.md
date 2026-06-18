# Mini Deep Agent local (Ollama)

Un agent minimal qui transforme un RAG classique en système agentique :
le LLM planifie, choisit ses outils, exécute en boucle, garde une mémoire
de travail sur disque et s'auto-corrige.

```
Question complexe
      ↓
Planner        → liste d'étapes (agent/planner.py)
      ↓
Boucle agentique (agent/executor.py)
  pour chaque étape :
    choix d'outil → exécution → réflexion → mémoire
      ↓
Synthèse finale → workspace/rapport.md
```

## Architecture

| Fichier | Rôle |
|---|---|
| `agent/llm.py` | Accès à Ollama (chat, chat JSON, embeddings) |
| `agent/planner.py` | Étape 1 — décompose la tâche en plan |
| `agent/tools.py` | Étapes 2-3 — registre d'outils (`TOOLS`) |
| `agent/rag.py` | Étape 7 — le RAG est un outil parmi d'autres |
| `agent/executor.py` | Étapes 4-6 — boucle, mémoire de travail, réflexion |
| `main.py` | Point d'entrée CLI + synthèse finale |
| `rag_engine/` | Moteur RAG modulaire (Parent-Child + Corrective RAG) interrogé par `agent/rag.py` |
| `documents/` | Corpus source, **une entrée unique organisée par dataset** : `documents/finance/`, `documents/droit/` |
| `workspace/` | Mémoire de l'agent : `plan.md`, `notes.md`, `rapport.md` |

> Le RAG n'est plus le mini-index NumPy d'origine : `agent/rag.py` est un adaptateur
> mince sur le moteur `rag_engine/` (retriever bge-m3 → parent-child → reranker + juge
> de pertinence LLM). Règle d'architecture : **une collection Qdrant par dataset, jamais
> combinées** — on choisit le corpus via `RAG__VECTOR_STORE__COLLECTION` (`dataset_finance`
> par défaut, `dataset_droit` pour les cours de droit).

## Prérequis

- **LLM du moteur RAG** : par défaut Claude via la passerelle OpenAI-compatible
  meai.cloud (`provider: openai` dans `rag_engine/configs/default.yaml`). La clé se
  met dans un `.env` gitignoré (`RAG__LLM__OPENAI__API_KEY=…`), jamais dans la config.
  Pour du 100 % local, basculer `provider: ollama`.
- [Ollama](https://ollama.com) lancé localement pour **l'agent** (`ollama pull qwen2.5:7b`)
  — et pour le moteur si tu choisis le mode local (`mistral:7b-instruct`).
- Python ≥ 3.11, le moteur RAG installé en éditable : `pip install -e ./rag_engine`
  (tire les dépendances de récupération : bge-m3, reranker, Qdrant)

## Utilisation

```bash
python main.py "Analyse les documents internes et fais un résumé des risques."
```

Les documents source vivent dans `documents/<dataset>/` (PDF). Pour ajouter un
corpus, déposez les fichiers dans `documents/<dataset>/` puis (ré)indexez avec le
moteur — voir `rag_engine/README.md`. L'outil `rag_search` de l'agent interroge la
collection configurée (un dataset à la fois).

## Tests & éval

Deux niveaux, testés séparément (le moteur RAG est un outil ; Harness le consomme) :

| Quoi | Où | Lancer |
|---|---|---|
| **Agent de bout en bout** — l'agent produit-il un bon rapport ? | `tests/run_golden.py` + `tests/golden_fonds_v1.yaml` | `python tests/run_golden.py` |
| **Récupération du moteur** — le RAG ramène-t-il les bons passages ? | `tests/rag_eval/` + `tests/golden/` + `tests/eval*.yaml` | voir ci-dessous |

```bash
# Métriques retrieval — corpus droit (rapide, sans LLM)
python -m tests.rag_eval.run --config tests/eval.yaml
# Métriques retrieval — corpus finance
python -m tests.rag_eval.run --config tests/eval_finance.yaml
# Comparatif des stacks (dense / hybrid / +reranker)
python -m tests.rag_eval.compare --config tests/eval.yaml --output compare_report.md
```

> Une config d'éval par dataset (`eval.yaml` = droit, `eval_finance.yaml` = finance) :
> on évalue chaque collection séparément — jamais combinées.
