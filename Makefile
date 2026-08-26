# Commandes courantes du dépôt. `make <cible>`.
.PHONY: help install test lint format run eval ablation accuracy

help:  ## Liste les cibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## Installe le moteur RAG (dépendances de récupération incluses)
	pip install -e ./rag_engine

test:  ## Tests déterministes de l'agent (rapides, sans réseau)
	pytest tests/unit

lint:  ## Vérifie le style (ruff)
	ruff check agent main.py tests/unit tests/agent_eval

format:  ## Reformate le code de l'agent (ruff format)
	ruff format agent main.py tests/unit tests/agent_eval

run:  ## Lance l'agent : make run Q="votre question"
	python main.py "$(Q)"

eval:  ## Éval bout-en-bout (golden set ; nécessite une clé API)
	python tests/agent_eval/run_golden.py

ablation:  ## Ablation à 5 bras : RAG → outils → plan → agent → juge (clé API)
	python tests/agent_eval/run_ablation.py --arms A,B,C,D,E

accuracy:  ## Justesse des réponses sur un rapport existant (aucun appel LLM)
	python tests/agent_eval/score_accuracy.py
