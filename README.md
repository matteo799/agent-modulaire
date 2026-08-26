# Modular Agent

A framework-free agent that turns a RAG pipeline into a tool-using, auditable workflow.
RAG is not the system, it is one tool out of 28.

[![CI](https://github.com/matteo799/agent-modulaire/actions/workflows/ci.yml/badge.svg)](https://github.com/matteo799/agent-modulaire/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![LLM](https://img.shields.io/badge/LLM-Claude%20Opus%204.8-D97757)
![Security](https://img.shields.io/badge/security-OWASP%20LLM%20Top%2010-2E7D32)

**Task.** Answer fund-analyst questions over French regulatory documents (KID/DICI) and NAV
histories: retrieve a figure, compute a risk ratio, produce a deliverable, often in one
request. Hard constraint: a wrong number is worse than no number.

**Evaluated** on 19 finance tasks across 9 capability categories, plus a 40-question
fund-manager set. Opus 4.8 selected the required tools in 14/15 cases, Haiku 4.5 in 12/15.
On the fund-manager run, answers were also scored for **correctness** rather than process:
69 of 70 assertions hold across 39 of 40 questions, against 29 % for a permuted-answer
control.

**Four findings, one of them negative:**

1. **A smaller model was not cheaper.** Haiku and Opus consumed 274 897 and 273 916 tokens
   on identical work, 0.4 % apart, with comparable median latency. Context volume is set by
   retrieved passages and tool output, not by model verbosity, so swapping the model does
   not move the bill. Haiku loses on tool routing and tail latency, not on price.
2. **The corrective retrieval loop (CRAG) bought nothing.** 19/30 answered in both modes,
   3/3 out-of-corpus traps refused in both. It changes 8 answers, but recovers and loses in
   equal measure, at the cost of one extra LLM pass per query.
3. **The only recurring failure is a prompt-enforced rule being ignored.** Across three
   runs, the sole consistent defect is the model doing arithmetic itself instead of calling
   `calculator`, despite an explicit rule forbidding it (Opus 1 of 3 arithmetic tasks, Haiku
   3 of 3). Every invariant enforced in code held; the one left to an instruction did not.

4. **Tool routing is a poor proxy for task success.** Scoring answers against ground truth
   recomputed from the dataset — no LLM in the grading loop — makes the two signals
   comparable per question. They agree on 29 of 32 and disagree on 3, and in all three
   disagreements *tool coverage is the one that misleads*: it passed a question whose answer
   shipped an incomplete fee schedule (a substring filter in `summary_text` silently dropped
   the performance fee — now fixed, with regression tests), and it failed two questions
   whose answers were correct. The converse is equally true, which is why both are kept: one
   of those "correct" answers is right only because the model bypassed `calculator` and got
   lucky, and accuracy alone cannot see that.

Finding 3 is the load-bearing one: it is measured evidence that "guarantee it in code, not
in a prompt" is an engineering constraint rather than a stylistic preference. Finding 4 is
the reason the evaluation grew a second axis. Protocol, matrices and limits:
**[`docs/benchmarks.md`](docs/benchmarks.md)**.

**Known gaps.** No automated accuracy score (correctness is read, not judged), no quantified
no-agent baseline, one run per arm, no production traffic. The component ablation
(RAG → +tools → +planning → full agent → +reflection) is specified and harnessed in
`tests/agent_eval/run_ablation.py` but **not yet run**, so no component-level claim is made
here.

---

## Why an agent and not retrieval

Plain RAG cannot express this, at any retrieval quality:

> Compare the management fees of three funds, compute the spread in percentage points
> between the most and least expensive, and write a report recommending the cheapest.

There is no mechanism for chaining three scoped retrievals, feeding the results into a
calculation and emitting a file. That gap is the reason for a planner and a tool loop, and
the overhead it costs on single lookups is visible in the token figures above.

The grounding constraint drives the rest. A KID contains no return series, so most risk
ratios genuinely cannot be computed from one. The system refuses instead of fabricating,
and that refusal is deterministic code, not a prompt instruction.

## Guarantees in code, not in prompts

"Never do X" in a prompt lowers the frequency of X without removing it. Wherever a behaviour
had to hold, it was taken from the LLM and given to the code.

| Behaviour | Prompt version | Structural version |
|---|---|---|
| Step reflection | "only judge real failures insufficient" produced constant false positives on a 7B and parasitic retries | deterministic rule: empty result, or one starting with `Erreur`. No LLM call. |
| Synthesis consistency | "add nothing beyond the deliverable", after which RAG chunks leaked back in | the memory is not passed once a deliverable exists, so the model cannot add to it |
| Arithmetic routing | "always use `calculator`" | not written yet, and it is the one that fails |

The reflection step in the diagram below is therefore a deterministic rule, not an LLM
judge. That was a reversal after the judge version kept marking correct results
insufficient, and it saves one LLM call per step. Reasoning:
[`docs/design-decisions.md`](docs/design-decisions.md) §5 and §9.

## Architecture

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

The core is domain-agnostic. Adding a domain takes a corpus in `documents/<dataset>/`
declared in `agent/datasets.py`, which gets its own sealed RAG collection, plus whatever
domain tools are needed in `agent/tools.py`, or none if `rag_search`, `read/write_file` and
`calculator` suffice.

The project started as a legal agent over French law course material, with `rag_search` as
its only tool, and was moved to fund rating without rewriting the core:

```
Legal agent  ──►  + finance dataset (KID/DICI prospectuses + Amundi NAV history)
             ──►  + metric_* tool family (Sharpe, Sortino, STARR, Martin…)
             ══►  Agent able to rate a fund
```

## Results per dataset

**Finance.** Retrieval measured over 30 questions, fast RAG against CRAG, 3/3 out-of-corpus
traps refused in both. End-to-end over 19 of the 20 tool-coverage questions, the
`multi-etapes` one not having been replayed in the last pass: tool coverage 14/15 for Opus
against 12/15 for Haiku. Separately, a 40-question fund-manager set at 31/33 coverage with
23 of 28 tools exercised. Ratio computation covered by unit tests.

**Law.** Golden set of 30 questions over three sources plus 3 out-of-corpus questions,
pinned to real chunk IDs. The harness computes recall@k, MRR, citation fidelity and RAGAS,
but no report is committed, so no retrieval score is claimed.

Per-question detail, with tools called, latency and tokens, is in
`tests/agent_eval/reports/`. Interpretation in [`docs/benchmarks.md`](docs/benchmarks.md).

## Layout

| Path | Role |
|---|---|
| `agent/` | `llm.py` (access, resilience, budget), `planner.py`, `tools.py` (28 tools), `executor.py`, `rag_adapter.py`, `security.py`, `audit.py` |
| `agent/finance/` | `metrics.py` (pure computation), `metric_catalog.py`, `select.py` (selection and clarification) |
| `main.py`, `app.py`, `demo.py` | one pipeline, three entry points: CLI, Streamlit chat, guided walkthrough |
| `rag_engine/` | RAG engine (bge-m3, parent-child, reranker, LLM relevance judge), self-contained |
| `documents/<dataset>/` | one folder per dataset; `amundi/` holds one folder per ISIN with `nav.csv` and `summary.json` |
| `workspace/` | agent memory, regenerated per run: `plan.md`, `notes.md`, `rapport.md` |
| `tests/` | `unit/` (fast, no network), `agent_eval/`, `rag_eval/` |
| `docs/` | architecture, design decisions, guardrails, metric reference, benchmarks |

## Run it

```bash
pip install -e ./rag_engine
echo 'RAG__LLM__OPENAI__API_KEY=sk-...' > .env     # gitignored, never in YAML

python main.py "Analyse les documents internes et fais un résumé des risques."
streamlit run app.py                                # live chat UI
python demo.py                                      # guided walkthrough, 3 questions
```

Config lives in `rag_engine/configs/default.yaml`, shared by agent and engine;
`RAG__SECTION__KEY` environment variables override it. `llm.provider` defaults to an
OpenAI-compatible gateway, `ollama` runs fully local. `vector_store.collection` selects the
corpus, one dataset at a time.

## Tests and evaluation

```bash
pytest tests/unit                                    # fast, no network, what CI runs
python tests/agent_eval/run_golden.py                # end-to-end, golden set
python tests/agent_eval/run_ablation.py --arms A,B,C,D,E   # component ablation
python tests/agent_eval/score_accuracy.py            # answer correctness, no LLM
python -m tests.rag_eval.run --config tests/rag_eval/configs/eval_finance.yaml
```

`run_golden.py` measures, per question, whether the expected tools were called, plus latency
and tokens, aggregated by category. Correctness is read rather than scored, since
`expected_answer` is a criterion and not an exact string.

`run_ablation.py` runs the same questions through five architectures, from plain retrieval
to the full agent with reflection, and scores refusal correctness and numeric grounding
deterministically. It is implemented and unit-tested against a stub LLM; it has not been run
against a live model, so this repository publishes no component-level results.

`score_accuracy.py` measures the second axis: not whether the right tools were called, but
whether the answer is right. Ground truth is recomputed from `documents/amundi/` with
`agent/finance/`, so no LLM takes part in the grading, and the score is produced from a
report that already exists — no API needed. It ships with a negative control that re-scores
each question against another question's answer; the score has to collapse, and it does.

## Security and observability

`agent/security.py` holds the input gate (jailbreak patterns plus a scope classifier), file
read/write confinement, an AST calculator that never calls `eval`, indirect-injection
neutralisation treating document content as data, and anti-obfuscation normalisation,
aligned with the OWASP LLM Top 10.

Runs are bounded by `AGENT_MAX_LLM_CALLS` and `AGENT_MAX_SECONDS`, and logged to
`logs/audit.jsonl` with query, security verdict, plan, every tool call with arguments and
result, usage and duration. Disable with `AGENT_AUDIT=0`. A failed LLM call degrades the run
rather than killing it.

## Documentation

| File | Contents |
|---|---|
| [`docs/benchmarks.md`](docs/benchmarks.md) | what the runs measured, what came out negative, what is not established |
| [`docs/architecture.md`](docs/architecture.md) | the system component by component |
| [`docs/design-decisions.md`](docs/design-decisions.md) | why each choice was made |
| [`docs/guardrails.md`](docs/guardrails.md) | refusal, honest computation, robustness |
| [`docs/metrics-reference.md`](docs/metrics-reference.md) | definitions of the 6 optimisation metrics |
| [`SECURITY.md`](SECURITY.md) | threat model, OWASP LLM Top 10 control table |
| [`demos/`](demos/) | replayable outputs, including 40 fund-manager questions over 474 funds |
| [`tests/README.md`](tests/README.md) | test map |
| [`rag_engine/README.md`](rag_engine/README.md) | the RAG engine as a reusable subpackage |

## Limits

The plan is frozen once set, with no global re-planning. Ingestion is manual. Arithmetic
routing is not enforced in code, which is the one known and measured hole. Nothing produces
more information than the corpus holds. There is no production traffic behind any of this:
no users, no request volume, no incident history.
