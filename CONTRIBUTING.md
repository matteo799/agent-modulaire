# Contribuer

> Projet sous licence propriétaire (voir `LICENSE`). Ces conventions valent pour
> le mainteneur et tout contributeur autorisé.

## Mise en place

```bash
pip install -e ./rag_engine        # moteur RAG + dépendances (make install)
echo 'RAG__LLM__OPENAI__API_KEY=sk-...' > .env   # jamais versionné
pre-commit install                 # hooks ruff (cf. .pre-commit-config.yaml)
```

## Boucle de développement

| Action | Commande |
|---|---|
| Lint | `make lint` (`ruff check agent main.py tests/unit`) |
| Format | `make format` |
| Tests déterministes (sans réseau) | `make test` (`pytest tests/unit`) |
| Éval bout-en-bout (clé API requise) | `make eval` |
| Lancer l'agent | `make run Q="votre question"` |

**Avant tout commit** : `make lint` et `make test` doivent passer (la CI les
rejoue — voir `.github/workflows/ci.yml`).

## Conventions

- **Python 3.11**, style imposé par `ruff` (config dans `pyproject.toml`).
- **Documentation en français**, comme le reste du dépôt.
- **Garanties structurelles, pas des prompts** : toute règle de sûreté ou de
  sécurité doit avoir un filet déterministe dans le code, et être consignée dans
  `GUARDRAILS.md` (avec son lieu d'application). Voir la philosophie du projet
  dans `CHOIX_DE_CONCEPTION.md`.
- **Tests pour toute partie déterministe** ajoutée (métriques, outils, sécurité,
  résilience, budget, audit) dans `tests/unit/`.
- **Un seul point de config LLM** : `rag_engine/configs/`. Ne pas coder en dur un
  modèle ou une clé.

## Où va quoi

| Type de changement | Emplacement |
|---|---|
| Nouvel outil de l'agent | `agent/tools.py` (dict `TOOLS`) + doc `architecture.md` §4 |
| Règle de sécurité / garde-fou | `agent/security.py` ou couche concernée + `GUARDRAILS.md` |
| Calcul de métrique | `agent/finance/` + tests `tests/unit/agent_finance/` |
| Moteur de récupération | sous-package `rag_engine/` (a son propre README) |

Documenter tout changement notable dans `CHANGELOG.md`.
