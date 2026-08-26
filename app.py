"""Interface web (chat) pour dialoguer avec l'agent en direct.

Lancement :
    streamlit run app.py

Réutilise tel quel le pipeline `main.answer_query()` (sélection métrique →
planification → boucle agentique → synthèse). En web il n'y a pas de `stdin`,
donc les clarifications de métrique (Sharpe vs Sortino…) sont résolues en mode
non bloquant via `select.auto_ask` (1re option, journalisée dans la trace).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from agent import datasets
from agent.finance import select as metric_select
from main import answer_query

# Journal des échanges (gitignoré via workspace/). Une ligne JSON par question :
# permet de relire après coup les questions posées et les réponses de l'agent.
CHAT_LOG = Path("workspace/chat_history.jsonl")


def log_exchange(question: str, answer: str, trace: dict, dataset: str = "") -> None:
    """Append-only : horodatage, dataset, question, réponse, et résumé de la trace."""
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "dataset": dataset,
        "question": question,
        "answer": answer,
        "metric": (trace or {}).get("metric"),
        "tools": (trace or {}).get("tools", []),
    }
    CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CHAT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

st.set_page_config(page_title="Agent finance", page_icon="", layout="centered")

st.title("Agent finance")
st.caption(
    "Posez une question sur les fonds / métriques de risque-rendement. "
    "L'agent planifie, exécute ses outils, puis synthétise une réponse sourcée."
)

# La liste des datasets vient du registre `agent.datasets` (source de vérité
# unique). Pour en ajouter un, on ne touche PAS ce fichier : on déclare un
# `register(Dataset(...))` dans agent/datasets.py et il apparaît ici tout seul.
DATASETS = datasets.all_datasets()

with st.sidebar:
    st.header("Dataset")
    dataset = st.radio(
        "Sur quel dataset porte ta question ?",
        DATASETS,
        format_func=lambda ds: ds.label,
        help="L'agent n'interroge qu'UN dataset à la fois (jamais les deux mélangés).",
    )
    st.caption(dataset.description)

# Historique de conversation persistant le temps de la session navigateur.
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{role, content, trace?}]


def render_trace(trace: dict) -> None:
    """Affiche ce que l'agent a réellement fait (transparence)."""
    if not trace:
        return
    with st.expander("Détail de l'agent (plan, outils, métrique)"):
        if trace.get("metric"):
            st.markdown(f"**Métrique retenue :** `{trace['metric']}`")
            if trace.get("clarification_asked"):
                st.caption(
                    "Clarification résolue automatiquement (web : pas de saisie "
                    "interactive — 1re option retenue)."
                )
        if trace.get("plan"):
            st.markdown("**Plan :**")
            for i, step in enumerate(trace["plan"], 1):
                st.markdown(f"{i}. {step}")
        steps = trace.get("steps") or []
        if steps:
            st.markdown("**Étapes exécutées :**")
            for s in steps:
                st.markdown(f"- `{s['tool']}` — {s.get('raison', '')}")


# Rejoue l'historique à chaque rerun Streamlit.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            render_trace(msg.get("trace"))

# Zone de saisie en bas de page.
if question := st.chat_input("Votre question…"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("L'agent réfléchit (planification → exécution → synthèse)…"):
            # On préfixe la question de la directive du dataset choisi : l'agent
            # sait de quel dataset on parle, l'utilisateur ne voit que sa question.
            directed_query = f"{dataset.agent_directive()}\n\n{question}"
            answer, trace = answer_query(
                directed_query,
                verbose=False,
                ask_fn=metric_select.auto_ask,
                return_trace=True,
            )
        st.markdown(answer)
        render_trace(trace)

    log_exchange(question, answer, trace, dataset=dataset.key)
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "trace": trace}
    )
