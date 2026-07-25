# Residual Risks And Open Problems

Last updated: 2026-07-25.

This is the canonical register of unresolved MARA benchmark and engineering
risks. It contains only work that still requires implementation or formal
closure evidence. Completed scheduler jobs, locally passing tests, changed
metric semantics, and arithmetically reproducible calculations are not by
themselves evidence that an answer is correct.

## Current Evidence

The frozen full-system baseline remains:

```text
/mnt/scratch/users/tbczhang/outputs/MARA/
final_thesis_benchmark_statistical_20260720_repair_g_fullsystem
```

The latest focused artifacts are:

```text
04_residual_validation/
├── residual-qasper-typed-v14-answerability-v7-semantic-single-l40s/
│   └── 01_core_text/20260724_233837_...-9917283
├── residual-finance-v13-slot-scale-direct-value-l40s/
│   └── outputs/20260725_010012_...-9917284
└── residual-alce-v9-safe-grounding-strict-single-a100/
    └── outputs/20260724_172225_...-9914331
```

Jobs `9917283` and `9917284` both completed with exit code `0:0`. QASPER has
159/159 usable predictions and Finance has 80/80; neither run has a route
timeout. Finance's formal wrapper records
`required_hybrid_eligible=12/12`, and its semantic judge has 100% coverage with
zero judge failures.

The implementation that produced these artifacts is commit `bd44996`
(`fix: close focused benchmark contract gaps`). The latest artifacts close the
old timeout-override, hybrid-eligibility projection, semantic-judge coverage,
and final-answer repetition concerns. Raw `predicted_answer` remains an
auditable generator field, while `answer_for_user` and `answer_for_scoring`
already remove repetition; the final duplicate rate is 0%. Those closed
concerns are no longer active problems below.

## Open Problem Summary

| ID           | Priority | Area                                       | Current evidence                                                                                                                                                       | Completion gate                                                                                                                                       |
| ------------ | -------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| FINANCE-001  | P0       | Retrieval, reranking, and route reporting  | V13 page hit 33.75%, all pages 23.75%, Candidate Recall@50 41.94%, Reranked Recall@10 25.83%; controller/CRAG hybrid selections are absent from Phase 3 reporting         | Page hit >=70%, all pages >=35%, effective hybrid/element coverage is formally reported, and required-slot evidence survives reranking                |
| FINANCE-002  | P0       | Value binding, rendering, and metric truth | V13 quality native 8.33%, all-operands/execution 16.67%, unit accuracy 58.33%; a year is accepted as an amount and a million result is rendered as billion                | Required slots are semantically bound, plans cover every slot, native >=20%, all operands >=50%, conditional execution >=95%, unit accuracy >=98%     |
| CONTRACT-002 | P1       | QASPER answerability and boolean polarity  | V14 native 55.41%, semantic 51.57%, structure 90.57%, evidence F1 21.66%; all 24 JSON repairs fail and boolean polarity remains unstable                                 | Gold-independent structure validity 100%, no verifier-induced regression, semantic F1 >=80%, and class diagnostics close yes/no/unanswerable failures |
| PERF-001     | P1       | Quality-preserving latency                 | Timeout is closed, but Finance average generation latency is 21.38 seconds and the quality gates still fail                                                              | Quality gates pass with zero required-row error; simple median increase <=20%, multipage/numeric <=50%, with P95 reported                             |
| EVAL-001     | P1       | Global release gate                        | Calibration and G-minus-B paired evidence remain incomplete                                                                                                             | Judge coverage >=99.5%, agreement >=90%, semantic gain >=8 points, paired CI lower bound >0                                                           |
| EVAL-002     | P2       | External evaluator                         | No fixed paper-grade external evaluator artifact                                                                                                                         | Frozen evaluator/provider contract and complete formal artifact                                                                                       |
| FORMAT-001   | P2       | Production formats                         | Loader smoke exists; preview/OCR/formula/chart E2E matrix remains incomplete                                                                                             | Required production-format matrix passes                                                                                                              |

Do not launch another full 3,540-prediction benchmark until `FINANCE-001`,
`FINANCE-002`, and `CONTRACT-002` pass their frozen focused subsets.

## FINANCE-001: Retrieval Regressed And Effective Hybrid Routes Are Misreported

### Evidence

Finance v13 reports:

- quality native numeric score: 8.33%;
- page hit: 33.75%;
- all-gold-pages hit: 23.75%;
- Candidate Recall@50: 41.94%;
- Reranked Recall@10: 25.83%;
- false abstention: 25%;
- zero route timeouts and 80/80 usable predictions;
- formal hybrid eligibility: 12/12.

The loss is already visible in the wide candidate pool and is compounded by
reranking. Text has candidate/reranked recall 30.8%/22.5%; controller and CRAG
each have 47.5%/27.5%. Phase 3 still reports both element and hybrid as
`not_evaluated`, even though controller and CRAG diagnostics record selected
hybrid routes.

### Root cause

There are two unresolved failures:

1. Retrieval recall is lost before final context construction. Required-slot
   restoration can recover a candidate ranked 31-80 only when that evidence
   entered the unique candidate pool and its slot binding is recognized. V13
   shows both a broad-recall loss and a further candidate-to-reranker loss, so
   MMR alone cannot repair it.
2. `phase3_multimodal_summary` recognizes only the top-level route IDs
   `element_rag` and `hybrid_rag`. It ignores the effective route selected
   inside controller/CRAG diagnostics. Consequently, an exercised hybrid route
   and its element-index coverage are reported as `not_evaluated`.

The previous eligibility-field and timeout causes are closed: the field now
survives artifact projection, the formal validator observes all 12 required
hybrid decisions, controller/CRAG index readiness requires element data, and
the explicit run timeout is honored.

### Required remediation

- Derive an additive `effective_route` from controller/CRAG selected-route
  diagnostics. Use it for Phase 3 hybrid participation and element-index
  coverage while retaining the top-level benchmark route for route-level
  quality comparisons.
- Add selected-route coverage to the report so a controller/CRAG row cannot be
  silently counted as text-only or disappear from modality diagnostics.
- Preserve the best semantically bound candidate for each required slot across
  reranking and final selection. This protection must be based only on query
  and slot semantics, never on benchmark gold pages.
- Publish candidate and reranked recall by top-level route and effective route,
  then inspect every lost required-slot evidence ID in the frozen subset.
- Keep retrieval-free `direct_answer` rows out of retrieval averages.

### Closure evidence

Every structured numeric example must either execute a genuinely available
hybrid route or explicitly fail hybrid eligibility. Phase 3 must report the
effective route and element coverage for controller/CRAG rows. On eligible
rows, page hit must reach 70%, all-gold-pages hit 35%, and Reranked Recall@10
must not regress from the last valid pre-v11 focused baseline. Text-only
fallback rows must be reported separately and cannot close this item.

## FINANCE-002: Numeric Binding And Rendered Units Can Contradict The Plan

### Evidence

Finance v13 improves quality native score from 0% to 8.33% and semantic F1
from 12.76% to 24.67%, but remains below every numeric closure threshold:

- all-operands, program, and execution accuracy: 16.67%;
- unit accuracy: 58.33%;
- false abstention: 25% overall and 33.3% on quality routes;
- slot coverage: 86.67%.

Three quality-route answers for `financebench_id_01928` are genuinely correct.
Two additional nominal native successes for `financebench_id_03031` render the
correct calculated value as `$5,818.0 billion` even though both operands and
the plan are in millions. Unit-aware audited native accuracy is therefore 5%,
not the reported 8.33%.

The artifact also exposes unsafe or avoidable binding failures:

- `financebench_id_00882` accepts the reporting year `2023` as the revolving
  credit amount and returns `$2,023`.
- `financebench_id_03531` binds `31` rather than the requested current-assets
  value, then safely abstains because source scale is missing.
- `financebench_id_04854` finds both free-cash-flow operands, but generic
  operand names do not inherit the single requested period and required-slot
  verification rejects the plan.

### Root cause

There are four concrete implementation defects:

1. `amount_after` takes the first number within 80 characters after a metric
   alias and does not exclude the requested period. A date such as
   `May 26, 2023` can therefore become a monetary operand.
2. `_operand_period` propagates a single question year only to `value`,
   `left`, and `right`, not to evidence operands such as
   `operating_cash_flow` and `capital_expenditure`.
3. `render_execution_answer` ignores `CalculationPlan.answer_scale` for
   difference, free-cash-flow, average, and working-capital templates and
   rescans the combined evidence text. An unrelated word `billion` can
   override a verified `million` plan after execution.
4. Stage metrics infer `unit_accuracy` only from verifier errors. They do not
   compare the rendered scoring answer with the plan's answer scale/unit, so
   the artifact can report a successful program and unit while exposing a
   dimensionally wrong final answer.

### Required remediation

- Exclude every question year from unlabeled monetary candidates and prefer
  values with an adjacent currency/scale marker or a labeled financial row.
  Reject rather than execute when the only candidate is a period.
- Propagate a single requested period to every evidence-backed operand. Keep
  explicit operand-name years authoritative for multi-period programs.
- Make the verified plan's `answer_scale` authoritative during rendering.
  Evidence-text scale inference is allowed only when the plan has no scale.
- Compare `answer_for_scoring` with `answer_scale` and `answer_unit` in stage
  metrics. A rendered mismatch must set `unit_accuracy=0` and identify
  `rendered_unit` as the failure stage.
- Keep the verifier's source-dimension and required-slot checks. Add a
  last-line rejection for an operand whose value is merely its period.
- Keep native numeric match as the final answer-quality authority; a safe
  verifier rejection is not counted as correctness.

### Closure evidence

Regression fixtures must cover the exact `$5,818 million` render, the PepsiCo
`2023` false amount, single-period free-cash-flow operands, the prior `23002%`
false success, dimension mismatch, incorrect evidence IDs, and rendered-unit
stage-metric coverage.

Every numeric example must emit a trace. All required slots must be represented
in the plan and covered by final citations. The frozen eligible subset must
reach all-operands 50%, native numeric 20%, false abstention at most 15%, and,
conditional on a valid complete plan, execution accuracy 95% and unit accuracy
98%.

## CONTRACT-002: QASPER Verifier Output Truncates And Polarity Is Unstable

### Evidence

QASPER v14 contains 159/159 usable predictions and reports:

- native/token F1: 55.41%, down 0.51 points from v13;
- semantic F1: 51.57%, down 0.63 points;
- gold-independent structure validity: 90.57%;
- evidence F1: 21.66%, unchanged;
- answerability verifier: 103 `ok`, 32 `not_required`, 24 `error`;
- JSON repair: 24 attempted, zero successful.

All 15 structurally invalid answers are free text on gold-unanswerable rows.
The 24 parser errors split across ten boolean and fourteen unanswerable
examples. A representative failed response already contains
`"verdict":"supported"` and a long grounded quote but is cut off before the
closing JSON delimiters; its repair response is truncated again.

### Root cause

The v7 trace and one-repair limit work, but two failures remain:

1. `_call_verifier` gives both the initial verifier and the JSON repair only 64
   output tokens, while the schema places no maximum length on
   `evidence_quote`. The model can satisfy the semantic instruction with a long
   quote but cannot close the JSON object. Repeating the same budget for repair
   deterministically repeats the truncation.
2. Boolean verification checks only whether the quote is a substring of the
   evidence. It does not check whether the quote contains enough question
   relation anchors or supports the returned polarity. The secondary verifier
   correctly remains advisory, so primary yes/no errors survive rather than
   being replaced by another model's unsupported guess.

### Required remediation

- Limit `evidence_quote` in both strict JSON schemas and instruct the verifier
  to use at most 20 words.
- Increase the bounded output allowance for the initial response and the
  structure-only repair. Keep exactly one repair and retain both raw responses
  in the trace.
- Apply the same gold-independent question-relation anchor check to boolean
  evidence quotes. If it fails, record `insufficient_evidence`; do not flip or
  erase the primary candidate.
- Do not restore secondary authority over non-empty boolean candidates.
- Improve boolean polarity at the primary prompt/model boundary and evaluate it
  on a frozen calibration set rather than using gold-aware post-processing.
- Report annotation-disagreement rows separately from parser failures.

### Closure evidence

Tests must prove that structure validity does not inspect the gold subtype,
unsupported quotes cannot confirm candidates, boolean advisory behavior is
unchanged, output budgets cannot truncate the bounded schema, and explicit
`unanswerable` remains stable.

The frozen subset must have 100% gold-independent structure validity, no net
verifier-induced paired regression, and semantic F1 at least 80%. If the
answer-quality target remains unreachable after evidence-quote validation,
the remaining limitation must be reported as model/retrieval capability rather
than repaired by gold-aware post-processing.

## PERF-001: Latency Evidence Must Remain Quality-Preserving

QASPER v14 average generation latency is 1.60 seconds and has zero timeouts.
ALCE v9 median is 4.61 seconds with P95 5.34 seconds. Finance v13 average
generation latency is 21.38 seconds and has zero timeouts.

The timeout defect is closed. Do not interpret text-only fallback, abstention,
incomplete plans, or rejected execution as a latency gain. Close this item only
after the corrected focused subsets pass quality gates, publish median and P95,
and stay within the fixed simple and multi-page/numeric latency budgets.

## EVAL-001: The Global Release Gate Is Not Measurable Yet

The old frozen G-minus-B QA semantic improvement is only +0.38 percentage
points and its confidence interval crosses zero.

Required closure:

1. Freeze a 200-example semantic calibration set, local judge model, prompt,
   parser, temperature, and thresholds.
2. Reach at least 90% human agreement and 99.5% parse coverage.
3. Re-run protected P0/P1 subsets with the evaluator enabled.
4. Rebuild B-through-G paired ablations only after dataset-specific gates pass.
5. Require G-minus-B QA semantic F1 of at least +8 points with paired 95% CI
   lower bound above zero and no protected-metric regression.

## EVAL-002: No Fixed Paper-Grade External Evaluator

The repository exposes evaluator interfaces and a local Qwen judge, but no
fixed external evaluator version and configuration has produced a complete
formal artifact.

Closure requires a frozen provider, model/version, prompt, parser, retry
policy, and cost budget, followed by calibration and formal runs that publish
coverage, failures, agreement, and the external primary metric.

## FORMAT-001: Production Format Robustness Is Incomplete

The current smoke establishes basic loader, index, and query behavior for PDF,
DOCX, PPTX, XLSX, CSV, Markdown, and text. It does not cover preview, Office
conversion, OCR, complex slide layouts, spreadsheet formulas, charts,
citations, and answer generation as one production matrix.

Closure requires frozen PDF, DOCX, PPTX, XLSX, CSV, Markdown, text, OCR, and
chart fixtures with separate loader, conversion, preview, indexing, retrieval,
citation, and QA results plus a format-specific failure taxonomy.

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

- Keep only unresolved problems as active sections.
- Remove an item only after its completion evidence exists.
- Add characterization or regression tests before changing Benchmark, DocQA,
  reporting, controller, or Slurm behavior.
- Do not refresh the code-hygiene baseline to make a gate pass.
- Link artifact directories instead of pasting large prediction payloads.
- Prefer artifact replay and focused frozen subsets before model reruns.
- Report metric coverage next to conditional success rates.
- Never use gold labels, gold pages, or gold answer types in runtime routing,
  evidence selection, answer generation, or verification.
