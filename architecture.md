# Architecture

*Ce document décrit **ce qu'est** le système et **comment** il fonctionne, composant
par composant. Pour le **pourquoi** de chaque choix (et les alternatives écartées),
voir `CHOIX_DE_CONCEPTION.md`, qui suit le même découpage en parties. Pour le détail
des règles de sûreté, voir `GUARDRAILS.md`.*

---

## 0. Vue d'ensemble

Le projet transforme un RAG classique (question → recherche → réponse) en **agent** :
le LLM **planifie**, **choisit ses outils**, **exécute en boucle**, garde une **mémoire
de travail** sur disque et **synthétise** une réponse finale. Le RAG n'est plus le cœur :
c'est **un outil parmi d'autres**.

```
Question
   │
   ├─ 0. Sélection de métrique        (si la question porte sur une métrique)   agent/finance/select.py
   │       └─ clarification éventuelle (Sharpe vs Sortino…) via ask_fn
   │
   ├─ 1. Planification → liste d'étapes                                          agent/planner.py
   │
   ├─ 2. Boucle agentique : pour chaque étape                                    agent/executor.py
   │       choix d'outil → exécution → réflexion → mémoire
   │       outils : rag_search · list_documents · read_file ·
   │               write_file · calculator · metric_*                            agent/tools.py
   │       le RAG est un outil → moteur rag_engine                               agent/rag_adapter.py
   │
   └─ 3. Synthèse finale → workspace/rapport.md                                  main.py
```

Deux niveaux de code, assumés :

| Niveau | Contenu | Dépendances |
|---|---|---|
| **Agent** (`agent/`, `main.py`) | Raisonnement écrit à la main : plan, choix d'outil, réflexion, mémoire. Aucun framework agentique. | Minimal — un client LLM. |
| **Moteur RAG** (`rag_engine/`) | Brique de récupération réutilisable (bge-m3 → parent-child → reranker + juge LLM). | Lourdes (sentence-transformers, Qdrant) — vues seulement à travers `agent/rag_adapter.py`. |

Le LLM de l'agent **et** du moteur est le même, configuré à un seul endroit
(`rag_engine/configs/default.yaml`). Par défaut : **Claude Opus 4.8** via la passerelle
OpenAI-compatible meai.cloud. Bascule possible sur Ollama (100 % local) ou un autre modèle.

---

## 1. Point d'entrée & orchestration (`main.py`)

CLI minimaliste : `python main.py "votre question"`. `answer_query()` enchaîne quatre temps :

1. **Sélection de métrique** (conditionnelle) — si `looks_like_metric_query()` détecte une
   intention de métrique, `select_metric()` résout *laquelle* et, en cas d'ambiguïté, **demande
   une clarification** (cf. §8). Le choix est injecté dans la planification.
2. **Planification** — `make_plan()` (cf. §4).
3. **Exécution** — `run()` (cf. §6).
4. **Synthèse** — `synthesize()` rédige la réponse finale dans un appel LLM séparé, **ancré sur
   le livrable** (le fichier écrit par l'agent) et non sur la mémoire brute. Trois garde-fous :
   refus déterministe si tout le RAG est revenu vide ; reformulation sans ajout/retrait ; repli
   gracieux si le LLM échoue (renvoie le livrable brut).

Le résultat est toujours écrit dans `workspace/rapport.md`. `ask_fn` est **injectable**
(`stdin_ask` interactif par défaut ; `auto_ask` non bloquant pour démos/éval).

**Workspace** — `workspace/` matérialise l'état mental de l'agent : `plan.md` (ce qu'il compte
faire), `notes.md` (ce qu'il a appris, persisté à chaque étape), `rapport.md` (sa conclusion).

---

## 2. Couche LLM (`agent/llm.py`)

Accès unique au modèle, partagé avec le moteur (`build_llm` lit la config `rag_engine`).

- **`chat(prompt, system, json_mode)`** — replie `system` en tête, envoie au modèle. En
  `json_mode`, ajoute une consigne JSON explicite.
- **`chat_json()`** — force et **parse** le JSON, avec parsing tolérant (`_parse_json` : extrait
  un bloc ```` ```json ````, découpe entre première et dernière accolade, `strict=False`) et
  **2 retries**.
- **Résilience réseau** — `chat()` rattrape toute `httpx.HTTPError`, réessaie quelques fois
  (backoff), puis lève **`LLMUnavailable`** (exception typée) plutôt qu'une stack trace. Les
  étages appelants la dégradent proprement (cf. §11).

---

## 3. Planificateur (`agent/planner.py`)

`make_plan(user_query, metric="", rationale="")` demande au LLM de décomposer la tâche en
**3 à 7 étapes**, chacune une phrase réalisable avec **un seul** outil. Le **catalogue d'outils**
(`tools_catalog()`) est injecté dans le prompt. Caractéristiques :

- **Décomposition multi-fonds** : pour une tâche sur plusieurs documents → une étape
  `list_documents` puis **une `rag_search` par fonds** (ciblée plus tard via `source`).
- **Dernière étape = livrable** (souvent `write_file`).
- **Indice de métrique** : si une métrique a été retenue en §0, le prompt cible explicitement
  l'outil `metric_<clé>`.
- **Parsing défensif** : accepte `{"steps":[…]}`, une liste nue, ou des étapes-objets
  renormalisées en phrase (`_step_text`).

---

## 4. Registre d'outils (`agent/tools.py`)

`TOOLS = {nom: {function, description}}` — un dict, pas un framework. `tools_catalog()` formate
les descriptions et les injecte dans les prompts (planner & sélecteur). **La description est la
seule information dont dispose le LLM pour choisir un outil et construire ses arguments** ; elle
dit aussi *quand NE PAS* l'utiliser.

| Outil | Rôle |
|---|---|
| `rag_search(query, top_k, source)` | Recherche sémantique dans le corpus PDF (→ §6). `source` restreint à un document (ISIN). |
| `list_documents()` | Liste les fonds/documents indexés (1ʳᵉ étape d'une comparaison). |
| `fund_summary(isin, fields)` | Faits d'un fonds **Amundi** lus dans `summary.json` (SFDR, SRI, benchmark, frais, gérant… — structuré, exact) — remplace `rag_search` pour ce dataset (→ §7). |
| `fund_stats(isin, rf)` | **Profil risque/rendement complet** d'un fonds Amundi calculé sur son historique NAV : rendement annualisé, volatilité, Sharpe/Sortino/STARR/Martin, max drawdown, CVaR (→ §7). |
| `fund_performance(isin, periods)` | **Performance par période** (YTD, 1 an, 3 ans, 5 ans, depuis création) — cumulée et annualisée, calculée sur la NAV. |
| `screen_funds(sort_by, top, …)` | **Screening / palmarès** : classe les fonds Amundi par critère (Sharpe, Sortino, rendement…) avec filtres (classe d'actifs, SFDR, SRI) → top N. |
| `read_file(path)` | Lit un fichier déjà connu (workspace ou documents). |
| `write_file(path, content)` | Écrit le livrable — **confiné à `workspace/`** ; recopie seulement, aucun calcul. |
| `calculator(expression)` | Évalue une expression arithmétique (`eval` neutralisé par liste blanche de caractères). Obligatoire pour tout calcul. |
| `metric_<clé>` ×6 | Outils métriques *rating fond* (→ §7), générés depuis le catalogue. |

L'agent **choisit ces outils en autonomie** d'après leur description : une question factuelle sur
un fonds Amundi → `fund_summary` ; un ratio → `metric_*` ; hors Amundi → `rag_search`.

**Convention de robustesse** : les outils **renvoient leurs erreurs en texte** (« Erreur : … »)
au lieu de lever — une erreur devient une observation que la boucle peut lire et corriger.

---

## 5. Boucle agentique (`agent/executor.py`)

Pour chaque étape du plan :

1. **Choix d'outil** (`choose_tool`) — un appel LLM reçoit : tâche globale, étape, catalogue,
   mémoire. Retourne `{"raison", "tool", "args"}`. La **`raison` précède le choix** (mini
   chain-of-thought qui réduit les choix absurdes ; inspectable dans les logs).
2. **Exécution** (`execute_step`) — appelle la fonction, rattrape les `TypeError` (mauvais args)
   en texte.
3. **Réflexion** (`reflect`) — **déterministe** : une étape est réussie sauf si le résultat est
   vide ou commence par « Erreur ». Aucun appel LLM. Si échec, une seule nouvelle tentative
   (`MAX_RETRIES = 1`) avec feedback.
4. **Mémoire** — liste `{step, tool, result}`, réinjectée dans chaque prompt (tronquée à
   1500 caractères), persistée dans `workspace/notes.md`.

**Robustesse** : si l'appel LLM de `choose_tool` lève `LLMUnavailable`, l'étape est marquée en
erreur et la boucle **continue** au lieu de planter (cf. §11).

---

## 6. RAG — récupération (`agent/rag_adapter.py` → `rag_engine/`)

`agent/rag_adapter.py` est un **adaptateur mince** : `rag_search` et `list_sources` renvoient des
**chaînes**, contrat inchangé pour le reste de l'agent. Sous le capot, le moteur enchaîne :

1. **Dense `bge-m3`** — embedding multilingue de qualité.
2. **Parent-Child** — indexe de petits *children* (précision), renvoie le *parent* (contexte).
3. **Reranker `bge-reranker-v2-m3`** — réordonne par pertinence réelle (plus gros gain qualité).
4. **Juge de pertinence LLM** (`grade_documents`, labels relevant/ambiguous/irrelevant) — écarte
   les passages hors-sujet ; si aucun ne subsiste → message « aucun passage pertinent ». C'est ce
   **filtre** (et non un seuil numérique) qui garantit le rejet d'une question hors corpus.

**Règle d'architecture** : **une collection Qdrant par dataset, jamais combinées**. Collection
active via `RAG__VECTOR_STORE__COLLECTION` (`dataset_finance` par défaut). Index **persisté** dans
`rag_engine/data/`, construit une fois à l'ingestion. Sortie = texte `[source]\ntexte` (traçable).

---

## 7. Couche métriques — *rating fond* (`agent/finance/`)

Expose chaque métrique d'optimisation de `metriques_optimisation_gold.md` comme **un
outil**. Trois modules :

| Module | Rôle |
|---|---|
| `metrics.py` | Calcul **pur** (sans LLM/I-O) : Sharpe/Sortino/STARR/Martin (forme scalaire + depuis série) et briques (vol annualisée, downside deviation, CVaR, Ulcer, max drawdown). |
| `metric_catalog.py` | **Source unique de vérité** : par métrique → formule, pénalise-hausse, tendance, **données requises**, quand l'utiliser, avantages/inconvénients + branchement de calcul. Génère aussi les descriptions d'outils. |
| `select.py` | Mappe l'intention → métrique ; **demande une clarification** quand deux se valent (`ask_fn`). |
| `amundi.py` | Accès au **dataset Amundi structuré** (`documents/amundi/<ISIN>/`) : `nav.csv` → série de rendements (vrai calcul des métriques) ; `summary.json` → faits (outil `fund_summary`). |

**Comportement d'un outil `metric_*`** (`build_metric_tool`), dans l'ordre : (1) calcule si une
série / des scalaires sont fournis ; (2) **si `source` est un ISIN Amundi → calcule le VRAI ratio
sur son historique NAV** (`nav.csv`) ; (3) sinon tente de lire R/σ dans un KID via le RAG
(best-effort) ; (4) sinon **garde-fou honnête** — explique sans inventer de chiffre. La famille
« budget » (CVaR/drawdown sous contrainte) est **explicative seulement** (le vrai calcul exige
un univers multi-fonds + matrice de rendements, hors périmètre).

**Clarification** : `select_metric()` renvoie la métrique retenue ; si ambiguë, `ask_fn(question,
options)` tranche — interactif (`stdin_ask`) en CLI, non bloquant (`auto_ask`) en démo/éval.

---

## 8. Garde-fous & robustesse

- **Garde-fous métier** — voir `GUARDRAILS.md` : récapitulatif unique de toutes les règles
  (rejet hors-corpus, `calculator` obligatoire, garde-fou métriques honnête, synthèse ancrée sur
  le livrable…), chacune indiquant son lieu d'application. Principe : *le corpus est le plafond
  d'information ; dire « je ne sais pas » est un succès, pas un échec.*
- **Robustesse réseau** — trois niveaux : retries du client moteur (tenacity, 3×) → filet agent
  + exception `LLMUnavailable` (`agent/llm.py`) → **dégradation gracieuse par étage** (sélection
  ignorée / message clair / étape marquée en erreur / repli sur le livrable brut). Un appel LLM
  qui échoue ne tue jamais tout le run.

---

## 9. Configuration (`rag_engine/configs/`)

`default.yaml` est la config de base ; `prod.yaml` surcharge quelques clés ; les variables
d'env `RAG__SECTION__KEY` priment sur tout.

| Clé | Valeur par défaut | Effet |
|---|---|---|
| `llm.provider` | `openai` | Passerelle OpenAI-compatible (Claude). `ollama` pour du 100 % local. |
| `llm.openai.model` | `claude-opus-4-8` | Modèle de l'agent **et** du moteur. |
| `llm.max_tokens` | `4096` | Plafond de génération (les nœuds courts surchargent plus bas). |
| `vector_store.collection` | `dataset_finance` | Corpus interrogé (un dataset à la fois). |

Clé API : jamais dans la config — via `.env` gitignoré (`RAG__LLM__OPENAI__API_KEY`).

---

## 10. Tests & éval

Système non déterministe → validation par golden sets et démos rejouables, plus des **tests
unitaires** sur les parties déterministes.

| Quoi | Où | Lancer |
|---|---|---|
| Métriques + outils + sélection + résilience | `tests/unit/` | `pytest tests/unit` |
| Agent de bout en bout | `tests/agent_eval/` | `python tests/agent_eval/run_golden.py` |
| Récupération du moteur | `tests/rag_eval/` | `python -m tests.rag_eval.run --config tests/rag_eval/configs/eval_finance.yaml` |

Carte détaillée des tests : `tests/README.md`.

---

## 11. Limites assumées

- **Plan figé** : pas de re-planification globale ; seule la correction locale par étape existe.
- **Ingestion manuelle**, hors agent (`python -m rag.ingestion.cli`).
- **Pas plus d'info que le corpus** : les ratios exigeant une série de rendements (Sortino, STARR,
  Martin) ne se calculent que si on **fournit** la série ; la famille « budget » et un `rf`
  variable dans le temps sont des extensions V2 (cf. `GUARDRAILS.md` → Limites).
- **Calcul multi-étapes : fiabilisé, pas garanti** (leviers de prompt, pas verrous durs).

*Chaque limite indique l'extension naturelle suivante. Justifications détaillées :
`CHOIX_DE_CONCEPTION.md`.*
