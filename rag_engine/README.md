# rag-engine — sous-package du projet Harness

> 📦 **Sous-package autonome.** Le point d'entrée du projet est le
> [`README.md` racine](../README.md) ; ce fichier ne documente que le **moteur RAG**
> en tant que brique réutilisable.
>
> Moteur RAG modulaire **Parent-Child + Corrective RAG**. Une collection PAR dataset, jamais combinées —
> corpus actuels : `dataset_finance` (prospectus) et `dataset_droit` (cours de droit).
> Les PDF sources vivent à la racine du dépôt dans `documents/finance` et
> `documents/droit` ; les index dérivés (Qdrant/SQLite) dans `rag_engine/data/`.

## Pourquoi ce repo

- **Sans hallucination** : grader de pertinence, vérification de grounding, fallback explicite « je ne sais pas ».
- **Modulaire** : 7 interfaces (Protocols) découplent retrieval, embedding, vector store, doc store, LLM, reranker, parsing. Changer de vector store = écrire une classe (qui implémente le Protocol) + une ligne de config.
- **On-prem ready** : embeddings et LLM open-weights, pas d'appel cloud obligatoire.
- **Petites PRs** : workflow pensé pour un dev assisté par Claude — quand un test casse, on sait quelle PR blâmer.

## Modularité : local ↔ API par composant

Chaque brique se choisit **local ou API** par configuration (provider), sans
toucher au code métier. Mêmes secrets via `.env` / variables d'env, jamais en clair.

| Composant | Local | API / serveur | Clé de config |
|---|---|---|---|
| **LLM** | `ollama`, `lmstudio` | `openai` (OpenAI-compat : Claude via meai.cloud, vLLM…) | `RAG__LLM__PROVIDER` (+ `…__OPENAI__BASE_URL/MODEL/API_KEY`) |
| **Embeddings** | `sentence_transformers` (bge-m3, in-process) | `openai` (`/v1/embeddings` : OpenAI, LM Studio, vLLM, Ollama via `/v1`) | `RAG__EMBEDDER__PROVIDER` (+ `…__BASE_URL/MODEL/API_KEY`) |
| **Reranker** | `bge` (cross-encoder) | `api` (`/rerank` Cohere/Jina-compatible) | `RAG__RERANKER__PROVIDER` (+ `…__BASE_URL/MODEL/API_KEY`) |
| **Vector store** | `qdrant` (local embarqué) | `qdrant` (serveur, `…__QDRANT__URL`) | `RAG__VECTOR_STORE__PROVIDER` |

Exemple — embeddings servis par Ollama au lieu de l'in-process :
```bash
RAG__EMBEDDER__PROVIDER=openai \
RAG__EMBEDDER__BASE_URL=http://localhost:11434/v1 \
RAG__EMBEDDER__MODEL=bge-m3  RAG__EMBEDDER__API_KEY=ollama  python …
```

> ⚠️ **Embeddings** : l'index Qdrant est lié au *modèle* d'embedding. Changer de
> fournisseur servant le **même** modèle (bge-m3) est gratuit ; changer de **modèle**
> impose de **ré-ingérer** le corpus (sinon l'espace vectoriel ne correspond plus).

## Où trouver quoi

| Besoin | Fichier |
|---|---|
| **Choisir les modèles** (LLM, embeddings, reranker) | [`configs/default.yaml`](configs/default.yaml) (sections `llm`, `embedder`, `reranker`) |
| **Paramètres RAG** (retrieval, reranker, CRAG) | [`configs/default.yaml`](configs/default.yaml) (sections `retrieval`, `crag`) |
| **Schéma typé + valeurs par défaut commentées** | [`src/rag/config/settings.py`](src/rag/config/settings.py) — la référence des paramètres |
| **Évaluation du moteur** (golden sets, runner) | **côté Harness** : `tests/rag_eval/golden/`, `tests/rag_eval/`, `tests/rag_eval/configs/eval*.yaml` — voir le `README.md` racine |
| **Vue d'ensemble du code** | section [Structure du repo](#structure-du-repo) plus bas |
| **Intégration dans l'agent Harness** | le `README.md` à la racine du dépôt + `agent/rag.py` |

> Ce moteur est **rapatrié comme module** dans le dépôt Harness : pas de `docs/`,
> de `Makefile` ni de `.env.example` ici — la configuration passe par les fichiers
> YAML de `configs/` et les variables d'environnement `RAG__SECTION__CLE`.

## Architecture en 30 secondes

```
PDF → Parse → Parent chunks (Doc Store)
                Child chunks  (Vector Store)
                     │
Question → Retrieve (Hybrid + ParentChild + Rerank)
              │
              ▼
       ┌──────────────────────────────┐
       │  LangGraph CRAG              │
       │  grade → decide              │
       │     ├─ relevant → generate   │
       │     ├─ ambiguous → refine    │
       │     └─ irrelevant → rewrite  │
       │  → ground_check              │
       └──────────────────────────────┘
              │
       Réponse + citations [doc:page]
```

---

## Roadmap — la marche à suivre pour construire ce RAG

Journal de construction du moteur, conservé comme historique des milestones
(chaque ligne correspondait à une PR du repo d'origine).

### Étape 0 — Squelette du repo (objectif : `pytest` passe sur un repo vide mais cohérent)

- [x] **M0.1** Init repo + `pyproject.toml` + `.gitignore` + `.env.example`
- [x] **M0.2** Ajouter `ruff`, `mypy`, `pre-commit` + hooks
- [ ] **M0.3** Workflow CI minimal (`.github/workflows/ci.yml`) lint + tests verts sur PR vide
- [x] **M0.4** Templates Issue + PR + CODEOWNERS + labels
- [x] **M0.5** `ARCHITECTURE.md` validé + ADR-0001 mergée
- [x] **M0.6** `CHANGELOG.md` initial

> **Tu es ici** une fois que le push initial est sur GitHub et que la CI tourne vert.

### Étape 1 — Interfaces & config (le contrat avant le code)

- [x] **M1.1** Types pydantic dans `rag.interfaces.types`
- [x] **M1.2** Protocols dans `rag.interfaces.protocols`
- [x] **M1.3** `rag.config.settings` (pydantic-settings + YAML)
- [x] **M1.4** `rag.config.factory` (dispatch sans adapters concrets)
- [x] **M1.5** Logger structuré (`structlog`) + contexte `query_id` (contextvars)

### Étape 2 — Ingestion baseline (ingérer un PDF, voir des chunks en base)

- [x] **M2.1** `PyMuPDFParser` : texte + métadonnées de page
- [x] **M2.2** Détection des sections (titres numérotés)
- [x] **M2.3** Chunker récursif (taille cible, overlap)
- [x] **M2.4** Stratégie Parent-Child : 1 parent → N children
- [x] **M2.5** `SQLiteDocumentStore` (parents)
- [x] **M2.6** `SentenceTransformersEmbedder` (BGE-M3)
- [x] **M2.7** `QdrantVectorStore` (upsert/search/delete/count)
- [x] **M2.8** CLI `scripts/ingest.py` : parse → embed → upsert
- [x] **M2.9** Idempotence (ré-ingérer ne duplique pas)

### Étape 3 — Retrieval composable (poser une question, récupérer des passages — sans LLM)

- [x] **M3.1** `DenseRetriever`
- [x] **M3.2** `BM25Retriever`
- [x] **M3.3** `HybridRetriever` (RRF)
- [x] **M3.4** `ParentChildRetriever` (dedupe parents, hydrate)
- [x] **M3.5** `BGEReranker` + `RerankingRetriever`
- [x] **M3.6** Endpoint `/search` debug (sans génération)

### Étape 4 — CRAG via LangGraph (le cœur anti-hallucination)

- [x] **M4.1** `LLMClient` adapter pour Ollama
- [x] **M4.2** Nœud `retrieve`
- [x] **M4.3** Nœud `grade_documents` (LLM-judge)
- [x] **M4.4** Nœud `decide` (table de décision déterministe)
- [x] **M4.5** Nœud `rewrite_query` (expansion acronymes)
- [x] **M4.6** Nœud `refine_knowledge` (knowledge strip)
- [x] **M4.7** Nœud `generate` (citations forcées)
- [x] **M4.8** Câblage du graphe + `max_iterations`
- [x] **M4.9** Nœud `ground_check` (vérif post-génération)
- [x] **M4.10** Nœud `fallback_no_answer`

### Étape 5 — API + DX (tu peux taper `curl /query` et obtenir une réponse citée)

- [x] **M5.1** `POST /ingest`
- [x] **M5.2** `POST /query`
- [x] **M5.3** Streaming `POST /query/stream` (SSE)
- [x] **M5.4** `GET /healthz` + `GET /readyz`
- [x] **M5.5** Middleware `query_id` + access logs

### Étape 6 — Évaluation + Observabilité (on mesure au lieu de deviner)

- [x] **M6.1** Golden set v1 (starter, à remplacer quand le corpus client sera ingéré)
- [x] **M6.2** Runner d'éval : retrieval metrics (recall@k, MRR, hit@k)
- [x] **M6.3** Runner d'éval : génération metrics (RAGAS faithfulness + answer_relevancy)
- [x] **M6.4** Métrique custom : citation accuracy
- [x] **M6.5** Job CI : eval fail si régression
- [x] **M6.6** Langfuse self-hosted + callback handler

### Étape 7 — Vector store Qdrant (preuve concrète de la modularité)

- [x] **M7.1** `QdrantVectorStore` adapter (passe la suite de tests du Protocol `VectorStore`)
- [ ] **M7.2** `docker-compose.dev.yml` : service Qdrant
- [x] **M7.4** Bench latence sur le golden set → `compare_report.md`
- [x] **M7.5** Bascule en prod via `configs/prod.yaml` (aucune ligne métier modifiée)

### Étape 8 — Itérations qualité (opt-in, à prioriser selon résultats M6)

- [ ] **M8.1** `UnstructuredParser` (tableaux)
- [ ] **M8.2** `MarkerParser` (formules)
- [ ] **M8.3** Mini-glossaire domaine pour `rewrite_query`
- [ ] **M8.4** Query routing (factuel vs résumé long)
- [ ] **M8.5** Cache embeddings (par hash de texte)
- [ ] **M8.6** Réindexation incrémentale (delta sur `source_file`)
- [ ] **M8.7** Filtres `classification_level` exposés dans l'API

---

## Quickstart

```bash
# 1. Installer le moteur (rapatrié dans Harness) en éditable, depuis la racine du dépôt
pip install -e ./rag_engine          # extras : .[dev], .[qdrant]… selon besoin

# 2. Configurer
# Aucun .env requis : défauts dans configs/default.yaml (Qdrant local embarqué +
# Ollama local). Surcharge ponctuelle via variables d'env RAG__SECTION__CLE.

# 3. Lancer Ollama (autre terminal)
ollama serve
ollama pull mistral:7b-instruct

# 4. Lancer l'API (depuis rag_engine/)
uvicorn rag.api.app:app --host 127.0.0.1 --port 8000

# 5. Ingérer un PDF — deux options équivalentes
#    via CLI (source unique : documents/<dataset> à la racine du dépôt) :
cp /chemin/vers/prospectus.pdf ../documents/finance/
python -m rag.ingestion.cli                       # défaut : documents/finance → dataset_finance
#    pour le droit : pointer une autre collection ET un autre dataset
RAG__VECTOR_STORE__COLLECTION=dataset_droit python -m rag.ingestion.cli -s ../documents/droit
#    via l'API :
curl -X POST http://localhost:8000/ingest \
  -F "file=@/chemin/vers/cours.pdf"

# 6. Poser une question (réponse synchrone, citée)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Quelle est la politique de distribution des revenus du produit SCPI ?"}'

# 7. Ou en streaming (Server-Sent Events)
curl -N -X POST http://localhost:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "Quels indicateurs de performance passée figurent dans le DIC ?"}'

# 8. Probes santé
curl http://localhost:8000/healthz   # process vivant
curl http://localhost:8000/readyz    # deps (Qdrant, Ollama) accessibles
```

Toutes les requêtes acceptent un header `X-Query-Id` ; s'il est absent
l'API en génère un et le renvoie dans la réponse — pratique pour corréler
les logs.

## Structure du repo

```
src/rag/
  interfaces/          # Protocols + types partagés. PERSONNE n'importe ailleurs.
  config/              # Pydantic settings + factory (seule à importer les adapters)
  adapters/            # Implémentations concrètes (Qdrant, Ollama, …)
  ingestion/           # Parse → chunk → embed → upsert
  retrieval/           # Dense / BM25 / Hybrid / ParentChild / Reranking
  graph/               # Nœuds LangGraph du CRAG
  generation/          # Prompts + post-processing (citations, grounding)
  api/                 # FastAPI (routers query / search / ingest / health)
  prompts/             # Templates Jinja2 versionnés
configs/               # YAML par environnement (default / prod)
```

> L'**évaluation** (golden sets + runner) ne vit pas dans le moteur : elle est
> côté Harness (`tests/`), qui consomme le moteur comme un outil.

## Statut

Milestones terminés : **M0 → M6, M7 (partiel — M7.1/M7.4/M7.5 ✓, M7.2 restant)**.
Prochaine étape : **M8** (qualité : parser tableaux, glossaire domaine, query routing).
Voir la roadmap ci-dessus pour le détail.

### Évaluation

Les commandes d'évaluation vivent **côté Harness** (`tests/rag_eval/`) — voir
la section « Tests & éval » du `README.md` racine. Résultats actuels du moteur :

Résultats actuels (corpus financier, 30 questions, k=5) :

| Config | hit@k | recall | MRR |
|---|:---:|:---:|:---:|
| dense | 93.3% | 81.7% | 0.711 |
| hybrid | 90.0% | 81.7% | 0.800 |
| dense+reranker | **100%** | **100%** | **1.000** |
| hybrid+reranker | **100%** | **100%** | 0.983 |

> Note : le reranker est transformateur sur les corpus courts (DIC de 3 pages)
> mais nécessite un GPU pour être viable en prod (~65 s/question en CPU).

## Licence

Propriétaire. Pas de redistribution.
