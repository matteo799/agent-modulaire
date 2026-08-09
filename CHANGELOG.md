# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Ce projet n'est pas versionné sémantiquement (démonstration) ; les entrées sont
regroupées par lot de travail.

## [Non publié]

### Ajouté
- **Budget de run (kill-switch)** — borne dure sur le nombre d'appels LLM et le
  temps mural par requête (`AGENT_MAX_LLM_CALLS`, `AGENT_MAX_SECONDS`) ;
  `BudgetExceeded` (sous-classe de `LLMUnavailable`) réutilise la dégradation
  gracieuse existante. (`agent/llm.py`)
- **Piste d'audit** — journal JSONL append-only par run (`logs/audit.jsonl`) :
  requête, verdict sécurité, plan, chaque étape (outil/args/résultat), usage,
  durée. Best-effort, désactivable `AGENT_AUDIT=0`. (`agent/audit.py`)
- **Fichiers de gouvernance du dépôt** : `LICENSE` (propriétaire), `SECURITY.md`
  (modèle de menace + contrôles OWASP LLM), `CONTRIBUTING.md`, ce `CHANGELOG.md`.
- Tests unitaires pour le budget et l'audit (`tests/unit/agent/test_budget_audit.py`).

### Modifié
- Documentation alignée sur le code : `architecture.md` §4 recense désormais les
  **28 outils** regroupés par famille (au lieu de ~11) ; `README.md` gagne une
  section « Sécurité, gouvernance & observabilité » ; `GUARDRAILS.md` documente le
  budget (§5.4) et la piste d'audit (§5.5).

## Antérieur (voir l'historique git)
- Couche 6 anti-détournement (OWASP LLM Top 10) : gate d'entrée, confinement
  fichiers, calculateur AST, neutralisation de l'injection indirecte.
- Interface Streamlit, registre de datasets, +13 outils, démo gérant 40 questions.
- Couche métriques *rating fond* (Sharpe/Sortino/STARR/Martin, budget CVaR/DD).
- Moteur RAG modulaire (bge-m3 → parent-child → reranker + juge LLM).
