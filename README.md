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
| `documents/` | Corpus indexé par le RAG |
| `workspace/` | Mémoire de l'agent : `plan.md`, `notes.md`, `rapport.md` |

## Prérequis

- [Ollama](https://ollama.com) lancé localement
- Modèles : `ollama pull qwen2.5:7b` et `ollama pull nomic-embed-text`
- Python ≥ 3.10 avec `pip install ollama numpy`

## Utilisation

```bash
python main.py "Analyse les documents internes et fais un résumé des risques."
```

Déposez vos propres fichiers `.md` / `.txt` dans `documents/` pour les rendre
accessibles à l'outil `rag_search`.
