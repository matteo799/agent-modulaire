# Modular Agent

A fund-analysis agent that plans, picks its own tools, and never invents a number.

[![CI](https://github.com/matteo799/agent-modulaire/actions/workflows/ci.yml/badge.svg)](https://github.com/matteo799/agent-modulaire/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![LLM](https://img.shields.io/badge/LLM-Claude%20Opus%204.8-D97757)
![Security](https://img.shields.io/badge/security-OWASP%20LLM%20Top%2010-2E7D32)
![License](https://img.shields.io/badge/license-all%20rights%20reserved-lightgrey)

A small agent written by hand, without an agentic framework, that turns a classical RAG
pipeline into something that can act: the LLM plans, chooses its tools, executes in a loop,
keeps a working memory on disk, and writes a final sourced answer. RAG is not the core of
the system any more, it is one tool out of 28.

The documentation is in French, since the domain is French retail-fund regulatory
documents. This README and [`docs/benchmarks.md`](docs/benchmarks.md) are in English.

## Why it exists

A fund analyst answering a client question usually has to do three things that retrieval
alone cannot do: pull a figure out of a regulatory document, compute something from a NAV
history, and produce a written deliverable. Often all three in one request.

> Compare the management fees of three funds in the corpus, compute the spread in
> percentage points between the most and least expensive, and write a report recommending
> the cheapest.

Plain RAG cannot express that task at any retrieval quality. There is no mechanism for
chaining three scoped retrievals, feeding the results into a calculation and emitting a
file. That gap is why there is a planner and a tool loop here.

The constraint that shapes everything else is that a wrong number is worse than no number.
A KID contains no return series, so most risk ratios genuinely cannot be computed from one.
The system is built so that this ends in a refusal rather than a plausible fabrication, and
that guarantee lives in code rather than in a prompt instruction.

## Does the complexity pay?

Having built the machinery is not evidence that it was worth building. The figures below
come from runs committed in this repository, including the ones that came out negative.
Protocol and full detail in [`docs/benchmarks.md`](docs/benchmarks.md).

A cheaper model turned out not to be cheaper. On 19 identical questions, Haiku 4.5 and Opus
4.8 consumed 274 897 and 273 916 tokens respectively, 0.4 % apart, with comparable median
latency. What fills the context is corpus passages and tool output, not the model's own
prose, so the context budget is a property of the architecture. Haiku loses on tool routing,
12/15 against 14/15, and on the tail of the latency distribution. It does not lose on price.

The corrective retrieval loop did not pay off either. Plain retrieval and CRAG both answered
19 of 30 questions and both refused 3 out of 3 out-of-corpus traps. CRAG changed 8 answers,
but the changes cancel: it recovers some and loses others it had previously answered
correctly. It costs an extra LLM pass per query, so it stayed an option rather than becoming
the default.

One failure mode recurs across all three runs, and it is the interesting one. The only
consistent defect is the model doing arithmetic itself instead of calling `calculator`, even
though the prompt forbids exactly that in capitals. The invariants that live in code, such
as out-of-corpus refusal, path confinement and the AST calculator, did not fail anywhere in
these runs. The one left to an instruction failed in all of them.

What the benchmarks do not establish is set out just as plainly in
[`docs/benchmarks.md`](docs/benchmarks.md): no automated accuracy score, no quantified
no-agent baseline, one run per arm.

## Guarantees in code, not in prompts

The recurring lesson of the project is that "never do X" in a prompt lowers the frequency of
X without ever removing it. Whenever a behaviour had to hold, it was taken away from the LLM
and handed to the code.

| Behaviour | Prompt version | Structural version |
|---|---|---|
| Step reflection | "only judge real failures insufficient", which produced constant false positives on a 7B and parasitic retries | a deterministic rule: empty result, or one starting with `Erreur`. No LLM call. |
| Synthesis consistency | "add nothing beyond the deliverable", after which RAG chunks leaked back in | the memory is simply not passed once a deliverable exists, so the model cannot add to it |
| Arithmetic routing | "always use `calculator`" | not written yet, and it is the one that fails |

The first row is worth reading twice, because the reflection step in the diagram below is a
deterministic rule and not an LLM judge. That was a deliberate reversal after the LLM-judge
version kept marking correct results insufficient, and it saves one LLM call per step. The
reasoning is in [`docs/design-decisions.md`](docs/design-decisions.md) §5 and §9.

## How it works

```mermaid
flowchart TD
    Q([Question]) --> G{Security gate<br/>jailbreak · scope}
    G -->|out of scope| STOP([Deterministic refusal])
    G -->|ok| S[0 · Metric selection<br/><i>asks for clarification if ambiguous</i>]
    S --> P[1 · Planning<br/>→ list of steps]
    P --> L{{2 · Agentic loop}}
    L --> T[Tool choice]
    T --> RAG[rag_search]
    T --> IO[read / write_file]
    T --> CALC[calculator AST]
    T --> MET[metric_*]
    RAG & IO & CALC & MET --> R[Deterministic check + memory<br/><i>no LLM call · workspace/</i>]
    R -->|next step| L
    R -->|plan complete| SYN([3 · Grounded synthesis<br/>workspace/rapport.md])

    classDef stop fill:#fde8e8,stroke:#c0392b,color:#7b241c;
    classDef done fill:#e8f6ef,stroke:#1e8449,color:#145a32;
    class STOP stop;
    class SYN done;
```

| Stage | Where |
|---|---|
| 0. Metric selection, with clarification if needed | `agent/finance/` |
| 1. Planning into a list of steps | `agent/planner.py` |
| 2. Loop: tool choice, execution, deterministic check, memory | `agent/executor.py`, `agent/tools.py` |
| 3. Final synthesis grounded on the deliverable | `main.py` |

## Changing domain

The core knows nothing about finance or law. Planning, the execution loop, working memory,
security and grounded synthesis are all domain-agnostic, so covering a new domain takes two
steps and no changes to the core.

First, drop a corpus into `documents/<dataset>/` and declare it in `agent/datasets.py`. It
then shows up on its own in the agent and the UI, with its own sealed RAG collection that is
never mixed with another. Second, add whatever domain tools are needed to `agent/tools.py`,
or none at all if `rag_search`, `read/write_file` and `calculator` are enough.

This project started as a legal agent. The first version targeted French law course material
in criminal law, civil procedure and public business law, and with `rag_search` as its only
tool it already answered questions sourced from the corpus and refused off-topic ones. It
was then moved to fund rating without rewriting the core:

```
Legal agent  ──►  + finance dataset (KID/DICI prospectuses + Amundi NAV history)
             ──►  + metric_* tool family (Sharpe, Sortino, STARR, Martin…)
             ══►  Agent able to rate a fund
```

Same planner, same loop, same memory, same guardrails, two very different domains.

### What was tested, per dataset

For the law corpus there is a golden set of 30 questions across the three sources, plus 3
out-of-corpus questions to check refusal, all pinned to real chunk IDs. The harness computes
recall@k, MRR, citation fidelity and RAGAS, but no report from it is committed, so no
retrieval score is claimed here. See `tests/rag_eval/golden/golden_droit_v1.yaml`.

For the finance corpus, three levels were run. Retrieval was measured over 30 questions
comparing fast RAG against CRAG, with 3 out of 3 out-of-corpus traps refused in both modes.
End-to-end behaviour was measured on 19 of the 20 questions in the tool-coverage set, the
`multi-etapes` question having not been replayed in the last pass, giving tool coverage of
14/15 for Opus 4.8 against 12/15 for Haiku 4.5; and separately on a 40-question fund-manager
set at 31/33 coverage with 23 of 28 tools exercised. Ratio computation is covered by unit
tests. See `demos/demo_comparaison.md`, `tests/agent_eval/reports/` and
`tests/unit/agent_finance/`.

Per-question detail, with tools called, latency and tokens, is in
`tests/agent_eval/reports/`. The full test map is in `tests/README.md`.

## Repository layout

A two-level monorepo: a hand-written agent, and a reusable RAG engine treated as a building
block.

| Path | Role |
|---|---|
| `agent/` | the agent itself: `llm.py` for LLM access, resilience and budget, plus `planner.py`, `tools.py` (28 tools), `executor.py`, `rag_adapter.py`, `security.py`, `audit.py` |
| `agent/finance/` | fund-rating metrics: `metrics.py` for pure computation, `metric_catalog.py`, `select.py` for selection and clarification |
| `main.py`, `app.py`, `demo.py` | entry points over one pipeline: CLI with final synthesis, Streamlit chat UI, guided walkthrough |
| `rag_engine/` | the RAG engine (bge-m3, parent-child, reranker, LLM relevance judge), self-contained with its own README |
| `documents/<dataset>/` | source corpora, one folder per dataset. `finance/` and `droit/` hold PDFs; `amundi/` holds one folder per ISIN with `nav.csv` and `summary.json` |
| `workspace/` | agent memory, regenerated on every run: `plan.md`, `notes.md`, `rapport.md` |
| `tests/` | `unit/` for fast pytest, plus `agent_eval/` and `rag_eval/` |
| `docs/` | architecture, design decisions, guardrails, metric reference, benchmarks |

## Quick start

```bash
# 1. Install the RAG engine (pulls retrieval deps: bge-m3, reranker, Qdrant)
pip install -e ./rag_engine

# 2. API key, in a gitignored .env at the root, never in versioned config
echo 'RAG__LLM__OPENAI__API_KEY=sk-...' > .env

# 3. Run the agent
python main.py "Analyse les documents internes et fais un résumé des risques."
```

Two other entry points share the same pipeline:

```bash
streamlit run app.py   # live chat UI, dataset picker, streamed trajectory
python demo.py         # guided walkthrough over 3 questions, every stage printed
```

Source documents live in `documents/<dataset>/`. To add a corpus, drop the PDFs in and
reindex with `python -m rag.ingestion.cli`, described in `rag_engine/README.md`.
`rag_search` queries one collection, so one dataset at a time.

## Configuration

Everything is set in `rag_engine/configs/default.yaml`, shared by the agent and the engine.
Environment variables of the form `RAG__SECTION__KEY` take precedence.

| Key | Default | Effect |
|---|---|---|
| `llm.provider` | `openai` | OpenAI-compatible gateway. `ollama` to run fully local. |
| `llm.openai.model` | `claude-opus-4-8` | model for both agent and engine |
| `llm.max_tokens` | `4096` | generation cap |
| `vector_store.collection` | `dataset_finance` | corpus queried; `dataset_droit` for law |

The API key only ever comes from `.env`, never from the YAML. For a fully local run, set
`provider: ollama` and `ollama pull qwen2.5:7b`. For a cheaper evaluation pass, set
`RAG__LLM__OPENAI__MODEL=claude-haiku-4-5`.

## Fund-rating metrics

Each metric in [`docs/metrics-reference.md`](docs/metrics-reference.md) is exposed as a tool,
`metric_sharpe`, `metric_sortino` and so on. They compute when given the inputs, either R and
σ or a return series, or read them from the document via `source` as an ISIN.

When computation is impossible, which is the normal case for a KID since it carries no
return series, the tool explains the metric and returns no number. Selection is driven by
intent: the planner picks the right ratio from the question, and asks for clarification when
two are equally defensible.

Rules are in [`docs/guardrails.md`](docs/guardrails.md) and
[`docs/architecture.md`](docs/architecture.md) §7.

## Security and observability

Each item below is enforced by code rather than by a prompt instruction. Enforcement points
are listed in [`docs/guardrails.md`](docs/guardrails.md).

`agent/security.py` holds the anti-hijacking layer: an input gate combining jailbreak
patterns with a scope classifier, file read and write confinement, an AST calculator that
never calls `eval`, neutralisation of indirect injection by treating document content as
data, and normalisation against obfuscation. It is aligned with the OWASP LLM Top 10.

Grounding treats the corpus as the ceiling on what can be said: refusal outside it is
deterministic, synthesis is grounded on the deliverable, and metrics return nothing rather
than something invented.

Runs are bounded by a hard budget on LLM calls and wall-clock time, through
`AGENT_MAX_LLM_CALLS` and `AGENT_MAX_SECONDS`, and logged to `logs/audit.jsonl` with the
query, security verdict, plan, every tool call with its arguments and result, usage and
duration. Logging is best-effort and can be turned off with `AGENT_AUDIT=0`. A failed LLM
call degrades the run rather than killing it.

## Tests and evaluation

The system is not deterministic, so the split is: unit tests over the deterministic parts,
golden sets for the rest, and replayable demos.

```bash
pytest tests/unit                                    # fast, no network, this is what CI runs
python tests/agent_eval/run_golden.py                # end-to-end agent over a golden set
python -m tests.rag_eval.run --config tests/rag_eval/configs/eval_finance.yaml
```

`run_golden.py` measures, per question, whether the expected tools were called, along with
latency and tokens, aggregated by category. Answer correctness is checked by reading, not
scored automatically, since `expected_answer` is a criterion rather than an exact string.
Results and their interpretation are in [`docs/benchmarks.md`](docs/benchmarks.md).

## Documentation

This README is the entry point; everything else sits under it.

| File | Contents |
|---|---|
| [`docs/benchmarks.md`](docs/benchmarks.md) | what the runs measured, what came out negative, and what the evaluation does not establish |
| [`docs/architecture.md`](docs/architecture.md) | what the system is and how it works, component by component |
| [`docs/design-decisions.md`](docs/design-decisions.md) | why each choice was made, from the start of the project |
| [`docs/guardrails.md`](docs/guardrails.md) | consolidated guardrails: refusal, honest computation, robustness |
| [`docs/metrics-reference.md`](docs/metrics-reference.md) | reference definitions of the 6 optimisation metrics |
| [`SECURITY.md`](SECURITY.md) | threat model and OWASP LLM Top 10 control table |
| [`demos/demo_Amundi.md`](demos/demo_Amundi.md) | the agent on 40 fund-manager questions over 474 funds, with the trajectory for each |
| [`demos/`](demos/) | other replayable outputs: 30 questions, RAG against CRAG, multi-step tasks |
| [`tests/README.md`](tests/README.md) | test map across `unit/`, `agent_eval/` and `rag_eval/` |
| [`rag_engine/README.md`](rag_engine/README.md) | the RAG engine as a reusable subpackage |

## Status and limits

This is a demonstration project, and the limits are deliberate. They are detailed in
[`docs/design-decisions.md`](docs/design-decisions.md) §11.

The plan is frozen once set, with no global re-planning. Ingestion is manual and happens
outside the agent. Arithmetic routing is not enforced in code, which is the one known and
measured hole, described in [`docs/benchmarks.md`](docs/benchmarks.md). Nothing produces more
information than the corpus holds, so ratios that need a return series are only computed when
one is supplied.

There is also no production traffic behind any of this: no users, no request volume, no
incident history. The evaluation above is offline, over fixed question sets, one run per arm.
