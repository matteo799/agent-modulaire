# Benchmarks

Building a planner, a tool loop and a corrective retrieval stage proves nothing on its own.
This file collects what the runs actually measured, including the parts that came out flat
or negative. Every figure comes from a report committed in this repository.

Three things came out of it:

- a cheaper model was not cheaper, it consumed the same tokens;
- the corrective retrieval loop did not improve the answer rate;
- one failure mode shows up in every run, and it is a failure of a prompt rule.

## Protocol

The corpus is fixed across all runs: Amundi KID/prospectus PDFs plus a NAV history per ISIN.
Two question sets are used. `question_test.yaml` has 20 questions across 9 categories, each
tagged with the tools it should trigger. `demo_gerant.yaml` has 40 questions written as
fund-manager scenarios.

`run_golden.py` drives everything in a single process, so the RAG index is built once and
reused and the embedding cost does not leak into per-question latency. It records, for each
question, whether the expected tools were actually called, wall-clock latency and token
count, then aggregates by category.

What it does not record is whether the answer was right. `expected_answer` in the YAML is a
criterion to read against, not a string to match, so correctness was checked by reading the
reports. This matters when interpreting anything below: "14/15" means the right tools were
called, not that the answers were correct.

Reproducing a run needs an API key:

```bash
python tests/agent_eval/run_golden.py
RAG__LLM__OPENAI__MODEL=claude-haiku-4-5 python tests/agent_eval/run_golden.py
```

## Model ablation

Same 19 questions, same corpus, same tools, same harness, only the model changes.

| | Opus 4.8 | Haiku 4.5 |
|---|---|---|
| Tool coverage | 14/15 | 12/15 |
| Distinct tools exercised | 10/11 | 10/11 |
| Metric selection | 5/5 | 5/5 |
| Out-of-corpus refusals | 2/2 | 2/2 |
| Total tokens | 273 916 | 274 897 |
| Median latency | 199 s | 189 s |
| Mean latency, excluding the 2 worst | 176 s | 244 s |
| Worst case | 541 s | 3 636 s |

Sources: [`golden_report_question_test_claude-opus-4-8.md`](../tests/agent_eval/reports/golden_report_question_test_claude-opus-4-8.md),
[`golden_report_question_test_claude-haiku-4-5.md`](../tests/agent_eval/reports/golden_report_question_test_claude-haiku-4-5.md).

The expected result was that the smaller model would be cheaper. It was not. Token counts
land within 0.4 % of each other, because what fills the context here is corpus passages and
tool output, not the model's own prose. The context budget is set by the architecture, so
swapping the model does not move it.

Median latencies are close too, and Haiku's is slightly lower. Where Haiku actually loses is
tool routing and the tail of the distribution: one question, `v2-16-budget-cvar`, took
3 636 s on its own.

That last figure needs a caveat. The Haiku pass hit gateway interruptions, so its worst case
measures the infrastructure as much as the model and should not be read as "Haiku is seven
times slower". The token equality and the coverage gap are not infrastructure artifacts, and
those are the two lines worth keeping.

## Retrieval strategy, a negative result

Same 30 finance questions, same corpus, same generation model. Fast mode is retrieval,
reranker, grounded generation. CRAG adds a grading pass over each passage, one query rewrite
if the passages are judged insufficient, and a grounding re-check.

| | Answered and cited | Out-of-corpus traps refused |
|---|:---:|:---:|
| Fast RAG | 19/30 | 3/3 |
| CRAG, max 1 rewrite | 19/30 | 3/3 |

Sources: [`demo_30_questions.md`](../demos/demo_30_questions.md),
[`demo_30_questionsCRAG.md`](../demos/demo_30_questionsCRAG.md),
[`demo_comparaison.md`](../demos/demo_comparaison.md).

The totals are identical. CRAG did change 8 of the 30 answers (Q2, Q4, Q6, Q9, Q11, Q13,
Q17, Q25), but the changes cancel out. It recovers answers on Q2 and Q4, and it loses Q6, a
question that fast mode had answered correctly with a full citation, a postal address and a
complaints procedure. After the rewrite, CRAG refuses it.

So the loop is neither free nor monotonic. On this corpus it swaps one class of answer for
another and adds an LLM pass per query to do it. That is why it stayed an option instead of
becoming the default.

Both modes refused all three out-of-corpus traps, which is the property that actually
matters here: grounding does not depend on the corrective loop.

## The failure mode that keeps recurring

Across three independent runs there is essentially one defect, and it is the same one each
time.

| Run | Failing questions | What happened |
|---|---|---|
| `question_test`, Opus | `v2-06-compare-sri` | expected `calculator`, called `rag_search` then `write_file` |
| `question_test`, Haiku | `v2-05-compare-frais`, `v2-06-compare-sri`, `v2-07-cout-pct` | same substitution, all three |
| `demo_gerant`, Opus, 40 Q | `g15-compare-frais`, `g18-sans-historique` | `g15` is the same substitution again |

In each case the model retrieved the right numbers and then did the arithmetic itself, in
the text it was writing, instead of calling the deterministic `calculator` tool. The answer
is often numerically correct, which is what makes it awkward: nothing in the output looks
wrong, and the substitution is only visible in the trace.

The reason this is worth more than the score is that the tool-selection prompt in
`agent/executor.py` already forbids it, in capitals:

> RÈGLE ABSOLUE sur les calculs : dès que l'étape implique une opération arithmétique […]
> tu DOIS choisir `calculator`. Ne fais JAMAIS le calcul toi-même, ni ici, ni plus tard dans
> `write_file`.

The rule is explicit and the model breaks it anyway, on one arithmetic task out of three for
Opus and three out of three for Haiku. Meanwhile the invariants that live in code rather
than in a prompt (out-of-corpus refusal, path confinement, AST-based evaluation) do not fail
anywhere in these runs. That is the argument for the design rule the rest of the project
follows, and here it has a measurement behind it rather than an opinion.

The fix is known and not yet written: detect an arithmetic expression in `write_file`
content and reject it at the tool boundary, the same way a path traversal is already
rejected. See [`design-decisions.md`](design-decisions.md) §9.

## What the agent adds over plain RAG

This is the first comparison anyone asks for, and the honest answer is that this repository
argues it rather than measures it.

The two are not scoreable on one question set, because they do not accept the same
questions. On a single lookup such as "what are the ongoing charges", the agent adds a
planning pass and a tool-selection pass to arrive at the same `rag_search` call. That is
pure overhead, and the token figures above are what it costs. The agent only earns its keep
where a task has to be composed:

> Compare the management fees of three funds, compute the spread in percentage points
> between the most and least expensive, and write a report recommending the cheapest.

No amount of retrieval quality gets plain RAG through that. It has no way to chain three
scoped retrievals, feed the results into a calculation and emit a file. The agent's trace
runs six steps, `list_documents`, three scoped `rag_search` calls, `calculator`,
`write_file`, and is recorded in [`demo_multi_tache.md`](../demos/demo_multi_tache.md).

The defensible claim is therefore about scope, not accuracy. The agent covers a class of
tasks plain RAG cannot express, and pays measurable overhead on the class where plain RAG
would have been enough. A production version would route between the two instead of sending
every question through the planner. That routing does not exist.

### The ablation that would settle it

`tests/agent_eval/run_ablation.py` puts the same questions through five architectures and
isolates one component at a time:

| Arm | Architecture | Isolates |
|---|---|---|
| A | one `rag_search`, then grounded synthesis | the retrieval baseline |
| B | a single tool-selection pass, no plan | A→B: tool use |
| C | planner and execution loop, no retry | B→C: planning |
| D | C plus deterministic reflection and one retry (production config) | C→D: the correction loop |
| E | D with an LLM judge replacing the deterministic rule | D→E: the cost of a semantic judge |

Security, grounded synthesis and the out-of-corpus guardrail are identical across all five,
so the only variable is the agentic architecture rather than the guardrails.

Scoring is deterministic, with no LLM judge anywhere in the measurement, which avoids both
the cost and the circularity of grading a model with a model. It records tool coverage,
refusal correctness on out-of-corpus questions, and a numeric grounding proxy: every number
in the final answer must appear in a tool result or in the question, and anything else is
flagged as unsupported. That proxy catches a figure conjured from nowhere, not a correct
figure used in the wrong place, and integers below 10 are ignored because they are
overwhelmingly step numbers and scales.

**This harness has not been run.** It is implemented and covered by unit tests against a
stub LLM, which verifies that all five arms execute, that arm C performs exactly one attempt
per step while arm D retries once, and that the grounding and refusal metrics behave as
described. Producing actual numbers needs 5 arms × 19 questions against a live model, and no
API access was available. **No component-level result is claimed anywhere in this
repository**, and the table above describes a protocol rather than a finding.

## What this does not establish

- There is no automated accuracy score. Coverage, latency and tokens are measured; whether
  the answer was right was checked by reading. No LLM judge, no exact matching.
- There is no quantified no-agent baseline. The section above argues the scope difference
  without measuring it.
- No component-level result exists. The five-arm ablation above is specified, implemented
  and unit-tested, but never executed against a live model, so nothing here says which
  component pays for itself. The retry policy being deterministic caps its cost at one extra
  attempt per failing step; the benefit remains unquantified.
- One run per arm, so no variance. With n=19 and a single sample, 14 against 12 is
  suggestive and nothing more.
- Token counts are estimates from the client's `count_tokens`, meant for comparing arms.
  No monetary cost is reported, because none was measured.
- No retrieval metrics are reported. The harness in `tests/rag_eval/` computes recall@k,
  MRR, citation fidelity and RAGAS against per-dataset golden sets, but no report from it is
  committed, so nothing here claims a retrieval score. Running it needs the local index
  rebuilt and an API key for the RAGAS judge.

## Next, in order

1. Close the arithmetic hole in code, then re-run `question_test` on both models. The
   prediction is falsifiable: coverage should reach 15/15 on both and the Opus/Haiku gap on
   this axis should disappear, which would mean it was never a capability gap at all, just
   an invariant nobody enforced.
2. Run the five-arm ablation. The harness is ready, so this is one command and an API key:
   `python tests/agent_eval/run_ablation.py --arms A,B,C,D,E`. The hypothesis worth stating
   in advance, so it can be wrong: most of the measured benefit will come from A→B, tool
   use, and C→D will be close to noise on this question set, because the deterministic
   reflection only fires on hard tool errors and those are rare.
3. Commit one `rag_eval` report so the retrieval claims rest on an artifact.
4. Three repetitions per arm, for a variance estimate on the coverage figures.
