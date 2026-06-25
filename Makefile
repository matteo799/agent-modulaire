# Commandes courantes du dépôt. `make <cible>`.
.PHONY: help install test lint format run eval

help:  ## Liste les cibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## Installe le moteur RAG (dépendances de récupération incluses)
	pip install -e ./rag_engine

test:  ## Tests déterministes de l'agent (rapides, sans réseau)
	pytest tests/unit

lint:  ## Vérifie le style (ruff)
	ruff check agent main.py tests/unit

format:  ## Reformate le code de l'agent (ruff format)
	ruff format agent main.py tests/unit

run:  ## Lance l'agent : make run Q="votre question"
	python main.py "$(Q)"

eval:  ## Éval bout-en-bout (golden set ; nécessite une clé API)
	python tests/agent_eval/run_golden.py
