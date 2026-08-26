# Benchmarks — does the agentic machinery earn its cost?

This document exists because "we built a planner, a tool loop, a reflection step and a
corrective RAG" is a feature list, not evidence. Every number below is extracted from a
run that is committed in this repository, and every claim links to the artifact it came
from. Where a result is negative or inconclusive, it is reported as such.

**Reader's shortcut — the three findings that matter:**

1. A cheaper model is **not** cheaper here. Haiku 4.5 and Opus 4.8 consumed the same
   token volume (0.4 % apart) on identical work; Haiku simply routed tools worse.
2. The corrective RAG loop (CRAG) **did not improve the answer rate** over plain RAG on
   30 questions. It costs an extra LLM pass and buys nothing measurable on this corpus.
3. One failure mode dominates every run: the model performs arithmetic itself instead of
   routing it to the `calculator` tool — **despite an explicit prompt rule forbidding it.**

---

## 1. Protocol

| | |
|---|---|
| **Corpus** | Amundi fund documents (KID/prospectus PDFs) + NAV history per ISIN. Fixed across all runs. |
| **Question sets** | `tests/agent_eval/question_test.yaml` (20 questions, 9 categories, each tagged with `expected_tools`) and `tests/agent_eval/demo_gerant.yaml` (40 questions, fund-manager scenarios). |
| **Harness** | `tests/agent_eval/run_golden.py` — single process, RAG index built once and reused, so embedding cost does not pollute per-question latency. |
| **Measured automatically** | Tool coverage (`expected_tools ⊆ tools actually called`), wall-clock latency, token count, per-category aggregates, tool-exercise matrix. |
| **Not measured automatically** | Answer correctness. `expected_answer` is a *criterion*, not an exact string — it is verified by reading. This is a real limitation, see §6. |

Reproducing a run (requires an API key):

```bash
python tests/agent_eval/run_golden.py                                           # default model
RAG__LLM__OPENAI__MODEL=claude-haiku-4-5 python tests/agent_eval/run_golden.py  # model ablation
```

---

## 2. Experiment 1 — model ablation

**Question:** on identical work, what does a smaller model actually cost you?

Same 19 questions, same corpus, same tools, same harness. Only the model changes.

| | Opus 4.8 | Haiku 4.5 |
|---|---|---|
| Tool coverage | **14/15 ✓** (1 ✗) | 12/15 ✓ (3 ✗) |
| Distinct tools exercised | 10/11 | 10/11 |
| Metric selection | 5/5 ✓ | 5/5 ✓ |
| Out-of-corpus refusals | 2/2 ✓ | 2/2 ✓ |
| **Total tokens** | **273 916** | **274 897** |
| Median latency | 199 s | **189 s** |
| Mean latency (excl. 2 worst) | **176 s** | 244 s |
| Worst-case latency | 541 s | **3 636 s** |

Sources: [`golden_report_question_test_claude-opus-4-8.md`](../tests/agent_eval/reports/golden_report_question_test_claude-opus-4-8.md) ·
[`golden_report_question_test_claude-haiku-4-5.md`](../tests/agent_eval/reports/golden_report_question_test_claude-haiku-4-5.md)

**Reading the result.** The naive expectation — "small model, fewer tokens, cheaper" —
does not hold. Token consumption is within 0.4 % across the two models, because token
volume here is driven by the *corpus passages and tool outputs fed into context*, not by
the model's own verbosity. The agent's context budget is a property of the architecture,
not of the model.

The median latencies are also comparable, and Haiku's median is marginally *better*.
Haiku loses in two specific places: tool-routing quality (§4) and the tail of the latency
distribution. One question alone (`v2-16-budget-cvar`) took 3 636 s.

**Caveat, stated plainly:** the Haiku pass suffered gateway interruptions. Its worst-case
latency therefore measures *infrastructure* at least as much as model speed, and should
not be read as "Haiku is 7× slower." The line worth keeping is the token equality and the
coverage gap — those are not infrastructure artifacts.

---

## 3. Experiment 2 — retrieval strategy ablation (a negative result)

**Question:** does a corrective retrieval loop (CRAG) beat plain retrieval?

Same 30 finance questions, same corpus, same generation model. Fast mode is
retrieval → reranker → grounded generation. CRAG adds: grade each passage, rewrite the
query if judged insufficient (max 1 rewrite), re-verify grounding.

| | Answered & cited | Out-of-corpus traps refused |
|---|:---:|:---:|
| Fast RAG | 19/30 | 3/3 |
| CRAG (max 1 rewrite) | 19/30 | 3/3 |

Sources: [`demo_30_questions.md`](../demos/demo_30_questions.md) ·
[`demo_30_questionsCRAG.md`](../demos/demo_30_questionsCRAG.md) ·
[`demo_comparaison.md`](../demos/demo_comparaison.md)

**Reading the result.** The headline numbers are identical. CRAG changed the answer on 8
of 30 questions (Q2, Q4, Q6, Q9, Q11, Q13, Q17, Q25), but the changes cancel out: it
recovers some answers (Q2, Q4) and *loses* others it had previously answered correctly
(Q6 — a question plain RAG answered with a correct, fully-cited address and procedure —
became a refusal after the rewrite).

So the corrective loop is not free and not monotonic: on this corpus it trades one class
of answer for another while adding an LLM pass per query. **It is kept as an option, not
as the default**, and this is the reason. A retrieval loop that reduces recall on
well-covered questions is a real risk, not a hypothetical one.

Both modes refused all 3 out-of-corpus traps, which is the property that actually matters
for this use case: the grounding guarantee does not depend on the corrective loop.

---

## 4. The dominant failure mode: arithmetic routing

Across three independent runs, the *same* failure appears, and almost nothing else does.

| Run | Failing questions | What happened |
|---|---|---|
| `question_test` / Opus | `v2-06-compare-sri` | expected `calculator`, called `rag_search` + `write_file` |
| `question_test` / Haiku | `v2-05-compare-frais`, `v2-06-compare-sri`, `v2-07-cout-pct` | same substitution, all three |
| `demo_gerant` / Opus (40 Q) | `g15-compare-frais`, `g18-sans-historique` | `g15` is again the same substitution |

In every case the model retrieved the right numbers, then **performed the arithmetic
itself inside the text it wrote**, instead of calling the deterministic `calculator`
tool. The answer is often numerically correct — which is precisely what makes this
dangerous: the failure is invisible in the output and only shows up in the trace.

**Why this matters more than the score.** The tool-selection prompt already contains an
explicit, capitalised rule (`agent/executor.py`):

> RÈGLE ABSOLUE sur les calculs : dès que l'étape implique une opération arithmétique
> […] tu DOIS choisir `calculator`. Ne fais JAMAIS le calcul toi-même, ni ici, ni plus
> tard dans `write_file`.

The rule is there, it is unambiguous, and the model violates it anyway — Opus on 1 of 3
such tasks, Haiku on 3 of 3. This is direct, measured evidence for the design principle
the rest of this repository is built on: **a property that must hold is enforced in code,
never by an instruction in a prompt.** Refusal, path confinement and AST-based evaluation
are enforced structurally and never fail in these runs. Arithmetic routing is enforced by
prompt, and fails.

This is the most useful thing these benchmarks produced, and it is an argument for
*removing* trust from the model, not for adding another agentic layer.

**Known fix, not yet implemented:** detect an arithmetic expression in `write_file`
content and reject it at the tool boundary, the way path traversal is already rejected —
turning a prompt rule into a code guarantee. See [`design-decisions.md`](design-decisions.md).

---

## 5. Experiment 3 — what the agent adds over plain RAG

This is the comparison a reader will ask for first, and it is the one this repository
answers **qualitatively rather than numerically**. Stating that honestly is more useful
than a fabricated table.

Plain RAG and the agent are not scoreable on the same question set, because they do not
accept the same questions. On single-lookup questions ("what are the ongoing charges?")
the agent adds a planning pass and a tool-selection pass to reach the identical
`rag_search` call — pure overhead, and §2's token figures are the cost of that overhead.
The agent's value appears only where the task requires *composition*:

> Compare the management fees of three funds, compute the spread in percentage points
> between the most and least expensive, and write a report recommending the cheapest.

Plain RAG cannot execute this at any retrieval quality: it has no mechanism to chain three
scoped retrievals, feed the results into a calculation, and emit a file. The agent's trace
for this task is 6 steps — `list_documents` → 3× scoped `rag_search` → `calculator` →
`write_file` — recorded in [`demo_multi_tache.md`](../demos/demo_multi_tache.md).

So the defensible claim is a **scope** claim, not an accuracy claim: the agent covers a
class of tasks plain RAG cannot express, and pays measurable overhead on the class where
plain RAG suffices. A production system should route between the two rather than send
every question through the planner. That routing does not exist yet.

---

## 6. What these benchmarks do *not* establish

Stated up front, because an evaluation that hides its own limits is not an evaluation.

- **No automated answer-accuracy score.** Coverage, latency and tokens are measured
  automatically; correctness is verified by reading the reports. There is no LLM judge
  and no exact-match scoring, so "14/15" means *the right tools were called*, never *the
  answer was right*. These are different things and the reports keep them separate.
- **No quantified no-agent baseline.** §5 argues the scope difference; it does not
  measure it. A rigorous version would run a plain-RAG arm and an agent arm over the
  question subset both can attempt, and compare accuracy per token.
- **No component ablation of the loop itself.** Planner-only vs planner+retry is not
  measured. The retry policy is deterministic (§4 of `design-decisions.md`), which bounds
  its cost to at most one extra attempt per failing step, but the benefit is unquantified.
- **Single run per arm.** No repetitions, so no variance estimate. With n=19 and one
  sample, a 14 vs 12 coverage difference is suggestive, not significant.
- **Token counts are estimates** from the client's `count_tokens`, intended for
  comparison between arms, not for billing. No monetary cost is reported because none was
  measured.
- **Retrieval metrics are not reported here.** The harness in `tests/rag_eval/` computes
  recall@k, MRR, citation fidelity and RAGAS against per-dataset golden sets, but no
  report from it is committed to this repository, so this document makes no retrieval
  quality claim. Running it requires rebuilding the local index and an API key for the
  RAGAS judge.

## 7. What I would measure next, in priority order

1. **Close the arithmetic hole in code**, then re-run `question_test` on both models. The
   prediction is falsifiable: coverage should go to 15/15 for both, and the Opus/Haiku
   gap on this axis should vanish entirely — which would mean the gap was never a
   capability gap, only an unenforced-invariant gap.
2. **Plain-RAG arm** on the question subset both architectures can attempt, scored on
   accuracy per token, to replace §5's qualitative claim with a number.
3. **Commit one `rag_eval` report** so the retrieval claims in the README are backed by an
   artifact rather than by a harness that exists.
4. **Three repetitions per arm** to attach a variance estimate to the coverage figures.
