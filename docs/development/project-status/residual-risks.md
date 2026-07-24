# Residual Risks And Open Problems

Last updated: 2026-07-24.

This is the canonical register of unresolved MARA benchmark and engineering
risks. It contains only problems that still require implementation or formal
closure evidence. A scheduler exit code, smoke result, replay-only gain, or
metric-contract change does not by itself close a release gate.

## Evidence And Baseline

The frozen full-system baseline remains:

```text
/mnt/scratch/users/tbczhang/outputs/MARA/
final_thesis_benchmark_statistical_20260720_repair_g_fullsystem
```

The latest focused validation artifacts are:

```text
04_residual_validation/
├── residual-qasper-typed-v11-answerability-v4-semantic-single-a100/outputs/
│   └── 20260724_153448_residual-qasper-typed-v11-answerability-v4-semantic-single-a100-9914072
├── residual-ragtruth-v17-source-support-single-a100/outputs/
│   └── 20260724_155055_residual-ragtruth-v17-source-support-single-a100-9914073
├── residual-finance-v10-parse-cache-execution-semantic-single-a100/outputs/
│   └── 20260724_160232_residual-finance-v10-parse-cache-execution-semantic-single-a100-9914074
└── residual-alce-v8-grounded-semantic-single-a100/outputs/
    └── 20260724_160947_residual-alce-v8-grounded-semantic-single-a100-9914075
```

All four Slurm jobs reached a terminal `COMPLETED 0:0` state. Artifact-level
completion differs:

- QASPER: 159/159 usable predictions.
- RAGTruth: 300/300 usable predictions.
- FinanceBench: 80/80 usable predictions.
- ALCE: 45/60 usable predictions and 15 execution errors.

The implementation that produced these artifacts is preserved by commit
`1c73905` (`fix: harden residual benchmark validation`). Before that commit,
the code-hygiene ratchet, changed-file pre-commit hooks, and 554 focused tests
passed.

## Problems Removed From This Register

The following items have formal completion evidence and are no longer open:

- Per-job LLM/retrieval ports and single-GPU service co-location. The final
  chain has no address collision, connection refusal, or disconnected peer.
- Semantic-evaluator alias launch. `local` is normalized to
  `local_qwen3_8b`, invalid Python paths fail before service startup, and all
  four replacement jobs entered benchmark execution.
- RAGTruth global contract gate. V17 has 100% valid JSON, zero execution
  errors, 70.29% positive recall, 91.98% clean specificity, and 68.58% span
  F1. These pass the fixed 99%/70%/90%/60% gates.
- MMDocRAG element identity and structure expansion. The completed v6 focused
  artifact retained canonical parent/hash metadata and passed the element
  retrieval gate used for this remediation wave.
- Duplicate-gain nDCG, parse-cache full-text preservation, route timeout
  diagnostics, and shared index reuse. Their regression and artifact-replay
  evidence remains valid.

RAGTruth subtype diagnostics remain useful: Summary positive recall is 37.04%
and Data2txt specificity is 88.89%. They are monitoring risks, not blockers for
the already satisfied global RAGTruth contract.

## Open Problem Summary

| ID             | Priority | Area                              | Current evidence                                                                                                           | Completion gate                                                                                                                                 |
| -------------- | -------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| EVAL-003       | P0       | Semantic score integrity          | Regression fixes and stored-claim replay pass locally; no post-fix live artifact exists                                    | Zero claim match returns 0, failed rows remain null, typed deterministic scoring is correct, focused live reports contain no false perfect rows |
| VALIDATION-002 | P0       | Artifact completeness             | Prompt budget and strict all-usable validator are implemented locally; no replacement ALCE artifact exists                 | Formal wrappers reject any failed/missing required row; frozen ALCE subset completes 60/60                                                      |
| FINANCE-001    | P0       | Retrieval, routing, and execution | Risk parity, required-hybrid preservation, aliases, period binding, and guarded traces are implemented locally             | Page hit >=70%, all pages >=35%, all operands >=50%, native >=20%, bound execution >=95%, false abstention <=15%                                |
| CONTRACT-002   | P1       | QASPER boolean contract           | V5 makes secondary boolean verdicts advisory and strengthens primary polarity instructions; no replacement artifact exists | No verifier-induced paired regression, structure validity 100%, semantic F1 >=80%                                                               |
| ALCE-001       | P1       | Answer grounding                  | V2 bounds the prompt and prevents unsafe non-empty answer rewrites; no replacement artifact exists                         | 60/60 usable, native >=75%, citation F1 >=93%, no paired correctness/semantic regression                                                        |
| PERF-001       | P1       | Quality-preserving latency        | Timeouts are removed, but Finance early abstention and ALCE execution errors invalidate closure                            | Zero required-row timeout/error and latency budget passes on quality-valid rows                                                                 |
| EVAL-001       | P1       | Global release gate               | Judge calibration and G-minus-B paired evidence remain incomplete                                                          | Coverage >=99.5%, agreement >=90%, semantic gain >=8 points with CI lower bound >0                                                              |
| EVAL-002       | P2       | External evaluator                | No fixed paper-grade external evaluator run                                                                                | Frozen evaluator contract and completed formal artifact                                                                                         |
| FORMAT-001     | P2       | Production formats                | Basic loader smoke passes; preview/OCR/formula/chart E2E coverage is incomplete                                            | Required production-format matrix passes                                                                                                        |

Do not launch another full 3,540-prediction benchmark until EVAL-003,
VALIDATION-002, FINANCE-001, CONTRACT-002, and ALCE-001 pass their frozen
focused subsets.

Current local remediation verification:

- New failing-first regressions cover semantic zero claims and error rows,
  Finance typing/routing/period/trace behavior, QASPER secondary-verifier
  authority, ALCE decision authority and prompt length, and strict artifact
  validation.
- The combined benchmark and affected DocQA suite passes 502 tests.
- The complete `libs/ktem/ktem_tests` suite passes 1,289 tests.
- The code-hygiene ratchet and changed-files pre-commit suite pass without
  refreshing the hygiene baseline.
- Stored-claim artifact replay records zero false-perfect zero-claim rows and
  zero scored execution-error rows for Finance v10 and ALCE v8.
- No post-fix formal Slurm artifact exists yet; these local results do not
  close the empirical dataset gates.

## EVAL-003: Semantic Score Integrity Is Broken

### Evidence

Finance v10 reports semantic F1 63.75% and judge coverage 100%, while native
numeric score and calculation execution are both 0%. Forty-eight free-text
rows receive semantic F1 1.0. The recurring judge payload is:

```text
gold_claim_count=1
supported_gold_claim_count=1
predicted_relevant_claim_count=0
supported_predicted_claim_count=0
```

ALCE v8 has the same defect. Several empty execution-error predictions receive
semantic F1 1.0, making the reported 70% semantic score unusable.

Finance also reaches the free-text judge because legacy manifests default to
`answer_type=extractive`. Sixteen rows are inferred as dates merely because a
descriptive gold answer contains a year. This bypasses the intended numeric
contract.

### Root cause

`semantic_answer._ratio(0, 0)` returns 1.0. The evaluator does not special-case
zero predicted claims, and the judge result validator permits the logically
inconsistent claim-count combination above. The runner also scores
execution-error rows like normal predictions.

Answer typing gives configured generic `extractive` precedence over Finance
metadata. Date inference uses a substring search instead of requiring the
complete gold answer to be a date.

### Implemented remediation and remaining validation

- Non-empty gold with zero predicted claims now receives precision, recall, and
  F1 0.
- Execution-error predictions return null semantic metrics with
  `judge_status=error` and remain in the coverage denominator.
- Finance `metrics-generated` examples use deterministic numeric scoring,
  including legacy generic-answer manifests.
- Date inference requires the complete answer to be date-shaped.
- Regression coverage protects all four cases before the production changes.
- Stored-claim replay on Finance v10 reduces the comparable semantic average
  from the invalid 63.75% to 4.69%; ALCE v8 comparable rows fall from the
  invalid 70% to 57.14%. Neither replay has a zero-claim perfect row or a scored
  execution-error row.

The replay intentionally reuses stored judge claim counts. One focused live
run is still required to validate the new type distribution, score coverage,
and judge coverage together.

### Closure evidence

The semantic regression suite must cover empty text, `unanswerable` against a
non-empty gold, judge zero-claim output, execution errors, Finance numeric
answers, descriptive answers containing years, booleans, dates, lists, and
formulas. Judge parse coverage and score coverage must be reported separately.

## VALIDATION-002: Completed Jobs Can Contain Incomplete Artifacts

### Evidence

ALCE job `9914075` is `COMPLETED 0:0`, but 15 of 60 prediction rows contain an
execution error. Five unique examples fail on all three routes. The Qwen server
reports a 4096-token maximum and requests with at least 3905 prompt tokens plus
192 completion tokens, for a total of 4097.

The current artifact validator fails only when every prediction is unusable.
One usable row is enough for the Slurm wrapper to exit successfully.

### Root cause

The ALCE grounding prompt concatenates up to eight 1800-character evidence
items and requests 192 output tokens. It has no total prompt budget and does
not reserve completion, schema, or tokenizer variance.

`validate_benchmark_predictions.py` checks nonzero usability rather than full
formal-subset usability. Scheduler success is therefore weaker than benchmark
completion.

### Implemented remediation and remaining validation

- The complete ALCE grounding prompt is bounded to 12,000 characters while
  keeping the 192-token completion budget. Evidence space is distributed
  across all selected items before prompt construction.
- The artifact validator now supports `--expected-count` and
  `--require-all-usable`.
- Formal text-route wrappers require every emitted prediction to be usable.
- Error rows remain written before the strict validator returns nonzero.
- Regression fixtures prove that partial artifacts and count mismatches fail.

The remaining action is a replacement frozen ALCE run. Only its 60/60 usable
artifact can close the runtime portion of this item.

### Closure evidence

The frozen 20-example, three-route ALCE subset must contain exactly 60 usable
rows and zero execution errors. An intentionally partial fixture must make the
validator and wrapper return nonzero.

## FINANCE-001: Structured Evidence Does Not Reach Deterministic Execution

### Evidence

Finance v10 measures:

- native numeric score: 0%;
- page hit: 33.75%;
- all-gold-pages hit: 22.5%;
- all operands bound: 0%;
- execution/program accuracy: 0%;
- false abstention: 27.5%;
- candidate recall@50: 39.17%;
- reranked recall@10: 34.17%.

The parse-cache repair is real: all 230 inspected evidence items have a
canonical ID and 228 have a page label. Stable table/cell identity is still
absent: table, row, and column fields are empty for all 230 items.

For the PepsiCo FY2021 capital-expenditure example, the answer page is 63 but
retrieval selects pages 53, 47, and 114. The planner recognizes a hybrid
question in local tests, but live cost-aware scoring records
`structured_calculation=false` and selects text. The question uses “capital
expenditure”; the filing row uses “Capital spending”. No
`finance_numeric_trace` is emitted because guarded retrieval returns before the
generation adapter runs.

### Root cause

There are four separate boundary failures:

1. The heuristic planner recognizes `amount` and `value`, but the cost-aware
   route scorer uses a narrower calculation vocabulary. The two controllers
   disagree about the same request.
2. Cost scoring can replace a required hybrid calculation route with text even
   when the QueryPlan requires structured operands.
3. Retrieval expansion and adequacy checks omit `capital spending` in some
   capital-expenditure alias sets.
4. Numeric trace creation occurs only inside generation. Retrieval guardrail
   abstention bypasses it, so a numeric attempt can disappear from executor
   observability.

The remaining identity limitation is upstream parsing: page text is now
preserved, but generic PDF text chunks cannot invent genuine table cell IDs.
Operand binding must therefore accept auditable page/element rows when cell
metadata is unavailable, while retaining lower identity confidence.

### Implemented remediation and remaining validation

- Planner and cost-aware scoring both recognize direct `amount`/`value`
  requests as structured calculation risk.
- When the planner selects hybrid for required operands and the route is
  available, cost scoring preserves it. Optional visual generation can still
  be skipped by backend capability gates.
- Retrieval expansion and adequacy checks now include `capital spending`.
- Direct-value extraction selects the requested fiscal period before using a
  first-row-value fallback.
- MARA records a failed deterministic numeric trace after guarded retrieval
  even when generation did not run.
- Page/element provenance remains valid; the code does not label generic page
  chunks as true table cells.

Local regressions cover the exact PepsiCo wording with a populated route probe,
the capital-spending alias, multi-period direct rows, and pre-generation
missing-evidence traces. A replacement Finance focused artifact remains
necessary because retrieval and operand gates are empirical.

### Closure evidence

Every numeric example must emit one trace. No descriptive/causal example may
activate the executor. Page hit must reach 70%, all-gold-pages hit 35%,
all-operands bound 50%, native numeric 20%, and false abstention at most 15%.
When operands are validly bound, execution accuracy must be at least 95% and
unit accuracy at least 98%.

## CONTRACT-002: QASPER Uses An Unreliable Second Model As Final Authority

### Evidence

QASPER v11 regresses from v10:

- native/token F1: 41.52% to 37.87%;
- semantic F1: 34.59% to 28.30%;
- structure validity: 47.17% to 35.22%;
- evidence F1: unchanged at 21.46%.

Relative to v9, native F1 is down 7.55 points and structure validity is down
27.67 points. Among 50 gold-`no` rows, none finish as `no`; 11 become `yes` and
39 become `unanswerable`. The v4 verifier emits 30 `yes`, one `no`, and 48
`insufficient_evidence` verdicts. Its only `no` verdict is on a gold-`yes` row.

Thirty-six of the 48 `insufficient_evidence` rows still have a gold-span hit.
Paired v10-to-v11 comparison has nine correct-to-wrong changes and only one
wrong-to-correct change.

### Root cause

The v4 verifier is a second generative classifier with authority to overwrite
the first answer. It receives selected evidence rather than the full paper and
is strongly biased toward `yes` or insufficient evidence. This compounds,
rather than independently corrects, the first generator's polarity error.

Broad document recall is not the main boundary: gold-span hit is 91.46%.
Evidence selection precision and paper-wide negative reasoning remain weak.
Top-k evidence cannot prove an absence-based `no`.

### Implemented remediation and remaining validation

- QASPER answerability v5 preserves a non-empty primary boolean candidate.
  Confirming, conflicting, and insufficient secondary verdicts remain visible
  through the new `action` trace field.
- The primary prompt explicitly forbids default-`yes` behavior and describes
  evidence that can support `no`.
- Non-boolean unsupported candidates retain the existing abstention contract;
  explicit primary `unanswerable` remains unchanged.
- Regression tests protect both polarity-conflict directions and insufficient
  secondary evidence.

The next focused run must report paired verifier actions. Bounded
full-document negative retrieval should be considered only if v5 removes the
regression but leaves absence-based questions below gate.

### Closure evidence

The verifier must introduce no net paired regression on the frozen set.
Applicable structure validity must be 100%, no answer may be derived from the
gold type, and semantic F1 must reach 80%. Until those gates pass, QASPER
remains diagnostic rather than a headline result.

## ALCE-001: Grounding Improves Citation But Regresses Correctness

### Evidence

The incomplete v8 report gives native 56.35% and citation F1 75%, both below
the 75% and 93% gates. On the 45 rows shared with v5:

- native increases from 74.12% to 75.13%;
- citation F1 increases from 86.67% to 100%;
- answer correctness falls from 61.57% to 50.26%.

Eighteen rows are marked `corrected`, representing six unique examples. Only
one unique correction is fully correct. The other five are wrong or partial.
All three routes produce effectively identical outputs.

### Root cause

Token traceability is necessary but not sufficient for relational support. A
wrong person, date, or episode can appear in the same evidence item and pass
the current subset-of-evidence-tokens check.

The grounding model can replace a non-empty candidate on `corrected` and can
turn a non-empty answer into `unanswerable` on `insufficient_evidence`.
Consequently, an uncertain second pass has more authority than the original
answer without demonstrating higher precision.

### Implemented remediation and remaining validation

- Grounding v2 preserves a non-empty candidate on insufficient evidence.
- Automatic correction is accepted only as recovery from an existing
  abstention; other corrections are retained as rejected telemetry.
- A `supported` verdict may bind its evidence ID but cannot rewrite the answer.
- Inconsistent supported answers and unsafe corrections have separate trace
  statuses.
- Prompt-budget and decision-authority regressions pass locally.

Re-run only through the strict validator added by VALIDATION-002. The new
artifact must establish both 60/60 completeness and paired quality behavior.

### Closure evidence

The frozen subset must complete 60/60 rows, reach native score at least 75% and
citation F1 at least 93%, and show no statistically or materially meaningful
paired correctness or semantic regression.

## PERF-001: Latency Evidence Must Be Quality-Preserving

QASPER, RAGTruth, and Finance v10 have zero route timeouts. Finance median
latency is 1.28 seconds but P95 is 10.51 seconds. ALCE median is 4.48 seconds,
but its 15 execution errors invalidate formal closure.

Do not interpret faster abstention or execution failure as a latency gain.
Close this item only when the corrected focused subsets have zero timeout and
execution errors, simple-QA median latency increases by at most 20%, and
multi-page/numeric median latency increases by at most 50%. Report P95 and
timeout-inclusive quality next to latency.

## EVAL-001: The Global Release Gate Is Not Measurable Yet

The old frozen G-minus-B QA semantic improvement is only +0.38 percentage
points and its confidence interval crosses zero. The latest semantic numbers
cannot replace that evidence because EVAL-003 invalidates part of the score.

Required closure:

1. Fix EVAL-003 and freeze the score contract.
2. Freeze a 200-example semantic calibration set, local judge model, prompt,
   parser, temperature, and thresholds.
3. Reach at least 90% human agreement and 99.5% parse coverage.
4. Re-run protected P0/P1 subsets with the evaluator enabled.
5. Rebuild B-through-G paired ablations only after dataset-specific gates pass.
6. Require G-minus-B QA semantic F1 of at least +8 points with paired 95% CI
   lower bound above zero and no protected-metric regression.

## EVAL-002: No Fixed Paper-Grade External Evaluator

The repository exposes evaluator interfaces and a local Qwen judge, but no
fixed external evaluator version/configuration has produced a complete formal
artifact.

Closure requires a frozen provider, model/version, prompt, parser, retry
policy, and cost budget, followed by calibration and formal runs that publish
coverage, failures, agreement, and the external primary metric. Until then,
scores must be described as local dataset-native, adapted, or diagnostic
rather than official leaderboard results.

## FORMAT-001: Production Format Robustness Is Incomplete

The current smoke establishes basic loader/index/query behavior for PDF, DOCX,
PPTX, XLSX, CSV, Markdown, and text. It does not cover preview, Office
conversion, OCR, complex slide layouts, spreadsheet formulas, charts,
citations, and answer generation as one production matrix.

Closure requires frozen PDF, DOCX, PPTX, XLSX, CSV, Markdown, text, OCR, and
chart fixtures, with separate loader, conversion, preview, indexing,
retrieval, citation, and QA results plus a format-specific failure taxonomy.

## Tracked Code Debt

These maintenance risks are not benchmark release claims:

- `ChatPage` still coordinates several workflows.
- Knowledge graph modules should not grow further.
- Preview and Office-conversion broad exception paths require actionable
  diagnostics.
- File-index Gradio event-chain order remains behavior and needs
  characterization coverage.
- Benchmark reporting metrics belong in focused helpers, not the runner.
- Shared artifact identity must remain the only controller, rescoring,
  synthesis, and cleanup matching rule.

## Update Rules

- Keep only unresolved problems in this document.
- Remove an item only after its completion evidence exists.
- Add characterization or regression tests before changing Benchmark, DocQA,
  reporting, controller, or Slurm behavior.
- Do not refresh the code-hygiene baseline to make a gate pass.
- Link artifact directories rather than pasting large prediction payloads.
- Prefer artifact replay and focused frozen subsets before model reruns.
- Report raw metric coverage next to conditional success rates.
