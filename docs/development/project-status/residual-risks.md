# Residual Risks And Open Problems

Last updated: 2026-07-24.

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
├── residual-qasper-typed-v13-answerability-v6-semantic-single-a100/
│   └── 01_core_text/20260724_183633_...-9914581
├── residual-finance-v12-hybrid-eligible-calculation-v1-l40s/
│   └── outputs/20260724_221924_...-9914582
└── residual-alce-v9-safe-grounding-strict-single-a100/
    └── outputs/20260724_172225_...-9914331
```

QASPER job `9914581` completed with exit code `0:0`; its artifact contains
159/159 usable predictions and zero route timeouts. Finance job `9914582`
generated 80 predictions, but only 78 are usable: controller and CRAG both
timed out on `financebench_id_10499` after the route manifest's 90-second
budget. The formal wrapper therefore rejected Finance v12 with exit code
`1:0`. Finance v12 is diagnostic evidence, not a closure artifact.

The implementation before this remediation is commit `ccb6197`
(`fix: repair focused benchmark failure chains`). The new failing-first
protection tests are commits `e16a737`, `ebe9de8`, and `1c3e0f0`; implementation
commit `239ee6b` produced the v13/v12 artifacts. The current remediation adds
failing-first coverage for the newly observed artifact projection, timeout,
element-index, rerank cutoff, QASPER JSON, direct-value, period-binding, and
scale-provenance failures. The P0/P1 items below remain open until replacement
artifacts meet their closure thresholds.

## Open Problem Summary

| ID           | Priority | Area                                   | Current evidence                                                                                                                                                                | Completion gate                                                                                                                                       |
| ------------ | -------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| FINANCE-001  | P0       | Retrieval and hybrid eligibility       | V12 page hit 46.25%, all pages 23.75%, Candidate Recall@50 49.14%, Reranked Recall@10 40.52%; hybrid ran, but the formal field was dropped and element candidates remained zero | A complete hybrid-eligible frozen run reaches page hit >=70%, all pages >=35%, and no required-hybrid question is silently evaluated as text-only     |
| FINANCE-002  | P0       | Slot binding and calculation semantics | V12 native 0%, all-operands 13.64%; correct Lockheed inputs were rejected, while PepsiCo source scale was inferred from unrelated page text                                     | Required slots are semantically bound, plans cover every slot, native >=20%, all operands >=50%, conditional execution >=95%, unit accuracy >=98%     |
| CONTRACT-002 | P1       | QASPER answer and scoring contract     | V13 native 55.92%, semantic 52.20%, structure 90.57%, evidence F1 21.66%; 24 verifier parse errors and one paired regression remain                                             | Gold-independent structure validity 100%, no verifier-induced regression, semantic F1 >=80%, and class diagnostics close yes/no/unanswerable failures |
| PERF-001     | P1       | Quality-preserving latency             | Finance v12 has two 90-second route timeouts and P95 generation latency 62.22 seconds                                                                                           | Quality gates pass with zero required-row error; simple median increase <=20%, multipage/numeric <=50%, with P95 reported                             |
| EVAL-001     | P1       | Global release gate                    | Calibration and G-minus-B paired evidence remain incomplete                                                                                                                     | Judge coverage >=99.5%, agreement >=90%, semantic gain >=8 points, paired CI lower bound >0                                                           |
| EVAL-002     | P2       | External evaluator                     | No fixed paper-grade external evaluator artifact                                                                                                                                | Frozen evaluator/provider contract and complete formal artifact                                                                                       |
| FORMAT-001   | P2       | Production formats                     | Loader smoke exists; preview/OCR/formula/chart E2E matrix remains incomplete                                                                                                    | Required production-format matrix passes                                                                                                              |

Do not launch another full 3,540-prediction benchmark until `FINANCE-001`,
`FINANCE-002`, and `CONTRACT-002` pass their frozen focused subsets.

## FINANCE-001: Hybrid Ran But Its Formal Proof And Element Evidence Were Lost

### Evidence

Finance v12 reports:

- native numeric score: 0%;
- page hit: 46.25%;
- all-gold-pages hit: 23.75%;
- Candidate Recall@50: 49.14%;
- Reranked Recall@10: 40.52%;
- false abstention: 23.75%;
- median generation latency: 14.44 seconds;
- P95 generation latency: 62.22 seconds;
- two route timeouts, leaving 78/80 usable predictions.

Controller and CRAG each selected hybrid for five examples. Their full
`agent_trace.planner_output.decision` records
`required_evidence_route_available=true`, and the Nike trace contains both
text and visual candidates. The top-level benchmark `controller_decision`
omits the field, so `--require-hybrid-eligible` observes `0/0` and cannot
certify the route. Element candidate count is zero on every Finance row, so
the exercised hybrid route is text plus page image rather than the required
text/page/element path.

### Root cause

There are four independent failures:

1. `mara_route_scorer` creates the eligibility field, but
   `ControllerDecision` neither stores nor serializes it. Artifact projection
   therefore drops an additive contract field that the formal validator needs.
2. `DocQAIndexCache.route_requires_element` recognizes only explicit element
   routes. Controller/CRAG configurations that allow `doc_element` reuse an
   index without requiring element records.
3. Required-slot selection starts after truncation to the first 30 reranked
   candidates. A necessary item at candidate rank 31-80 cannot be restored,
   even though the later MMR stage protects already-selected slots.
4. An explicit 240-second focused-run timeout is overwritten by each manifest
   route's 90-second value. Both timeout rows are the same multi-step inventory
   turnover example.

### Required remediation

- Record a distinct `required_hybrid_unavailable` route decision and an
  explicit eligibility field whenever a structured calculation requires
  hybrid evidence but no complementary modality has usable candidates.
- Preserve the eligibility field through `ControllerDecision`, runtime
  response, benchmark prediction, and the formal validator.
- Treat controller/CRAG routes that allow `doc_element` as requiring an element
  index during shared-index readiness checks.
- Build the final 30-candidate shortlist from the strong rerank plus one
  protected best match for every required slot. Protection must be based only
  on query/slot semantics, never gold pages.
- Make an explicit run-level timeout override a lower template timeout; retain
  the route template value only when no run-level value is supplied.
- Report retrieval by stage and by eligible route. Do not average the
  retrieval-free `direct_answer` diagnostic into QA retrieval claims.
- Inspect the candidate-to-reranked losses on the frozen examples. Preserve
  required-slot evidence through final selection, but do not use gold pages or
  benchmark labels at runtime.

### Implemented in this remediation

- Structured calculations that request `hybrid` now emit
  `required_hybrid_unavailable` and
  `required_evidence_route_available=false` when complementary evidence is not
  available.
- The formal artifact validator has an opt-in
  `--require-hybrid-eligible` gate. It fails when no required-hybrid decision
  was exercised or when any such decision was unavailable.
- `multimodal_route_rerun.sbatch` can enable this gate with
  `MARA_MULTIMODAL_REQUIRE_HYBRID_ELIGIBLE=1` and validates every prediction
  before deleting its isolated runtime.
- The current implementation carries
  `required_evidence_route_available` through `ControllerDecision`, requires
  an element-ready index whenever controller/CRAG allows `doc_element`,
  restores required-slot matches from candidate ranks 31-80 before MMR, and
  makes an explicit run timeout override template route timeouts.

### Still open

The v12 artifact is incomplete and its top-level eligibility proof is absent.
Retrieval improved substantially but remains below the fixed page thresholds,
and the candidate-to-reranked loss still removes the only Nike operand
evidence. This item remains P0 until a complete replacement artifact proves
element availability, hybrid eligibility, and the frozen retrieval gates.

### Closure evidence

Every structured numeric example must either execute a genuinely available
hybrid route or explicitly fail hybrid eligibility. On eligible rows, page hit
must reach 70%, all-gold-pages hit 35%, and Reranked Recall@10 must not regress
from the last valid pre-v11 focused baseline. Text-only fallback rows must be
reported separately and cannot close this item.

## FINANCE-002: Source Dimensions And Direct Numeric Intents Remain Incomplete

### Evidence

Finance v12 still has 0% native numeric score. All-operands and program/
execution accuracy fall to 13.64%; unit accuracy is 86.36%.

The prior Nike `23002%` false success is now rejected as missing operands, so
the incomplete-plan verifier repair is effective. The replacement artifact
exposes new downstream failures:

- PepsiCo binds raw `-4625` from a free-cash-flow table. The evidence page also
  mentions unrelated debt amounts in billions, so whole-page scale scanning
  assigns the operand scale `billion`. The executor then renders
  `$4,625 billion` instead of converting source millions to approximately
  `$4.625 billion`.
- Lockheed binds the correct 19,815 and 13,997 values from a page headed
  `(In millions)`. The generic operand names `left` and `right` do not inherit
  FY2021, so required-slot verification rejects both despite correct evidence.
- General Mills selects one operand from the cash-flow statement with an
  explicit million scale and another repeated value from a summary table with
  no local scale, producing a safe but avoidable scale mismatch.
- Direct total-current-assets and net-property-plant-equipment questions are
  classified as `unsupported_formula`, although each requires one traceable
  value rather than a formula.

### Root cause

There are five remaining validation gaps:

1. Source scale extraction scans the entire evidence page and prefers
   `billion` by fixed order, so unrelated narrative can override a table's
   actual or missing scale.
2. A plan that requests conversion to an explicit answer scale remains valid
   when the source operand scale is unknown.
3. Generic formula operand names do not consistently inherit the single
   target period from the question.
4. Evidence matching ranks by value and period only. It does not prefer the
   candidate that also provides the operand metric and explicit table scale.
5. Finance metric aliases and direct-value handlers do not cover current
   assets, serial-comma property/plant/equipment variants, and similar
   one-cell questions.

### Required remediation

- Treat `CalculationOperand.scale` strictly as source scale and
  `CalculationPlan.answer_scale` as target scale.
- Infer source scale only from structured metadata, explicit table headers, or
  the local metric/value clause. Never infer it from unrelated page text or
  from the question's requested answer scale.
- Reject explicit scale conversion when any contributing evidence operand has
  unknown source scale.
- Rank value matches by metric support, period, and explicit source dimension;
  prefer one evidence item that contains all operands of the same table when
  available.
- Propagate a single question period to formula operands such as `left/right`
  and direct `value`.
- Extend canonical aliases and direct-value execution for current assets,
  property/plant/equipment variants, and other one-value Finance intents.
- Keep native numeric match as the final answer-quality authority; a safe
  verifier rejection is not counted as correctness.

### Implemented in this remediation

- Numeric slot binding now requires at least 0.75 canonical metric-alias token
  coverage in addition to period and numeric evidence.
- Multi-period “cost of goods sold as a percentage of revenue” questions build
  cost-of-goods-sold and revenue slots for every requested year, then execute
  annual ratios, multiply by 100, and average the percentages.
- The numeric adapter receives the bound QueryPlan. The verifier checks every
  required operand slot against a distinct plan operand, its period, metric,
  and allowed evidence identity.
- Missing versus explicit scale, unit, or currency is now a compatibility
  error. Stage metrics require a valid complete plan before reporting
  `all_operands_bound=1`.
- Annual value parsing no longer crosses sentence boundaries and binds the
  next year's number to the prior year. A fallback remains only when no
  sentence-level annual fact exists, preserving horizontal financial rows.
- The current implementation treats operand scale as source scale, recognizes
  explicit table headers before local metric clauses, and refuses explicit
  scale conversion when source scale is missing. Unrelated page-level scale
  words can no longer authorize a conversion.
- Evidence binding now prefers candidates with the requested metric and an
  explicit source scale. Single-period working-capital operands inherit the
  question period.
- Direct current-assets, property/plant/equipment, and revolving-credit
  capacity intents now have canonical aliases and deterministic one-value
  execution paths.

### Still open

V12 proves that incomplete plans are no longer reported as successful, but no
formal artifact has yet met native numeric, all-operands, conditional
execution, unit, or false-abstention thresholds. The new source-scale and
direct-value regressions must pass locally, then a complete frozen run must
show that safety fixes also improve answer quality.

### Closure evidence

Regression fixtures must cover the exact 23002% failure, missing periods,
unrelated year-number tables, multi-period percentage-of-revenue programs,
dimension mismatch, incorrect evidence IDs, and stage-metric coverage.

Every numeric example must emit a trace. All required slots must be represented
in the plan and covered by final citations. The frozen eligible subset must
reach all-operands 50%, native numeric 20%, false abstention at most 15%, and,
conditional on a valid complete plan, execution accuracy 95% and unit accuracy
98%.

## CONTRACT-002: QASPER Verifier Parsing And Primary Polarity Remain Unresolved

### Evidence

QASPER v13 contains 159/159 usable predictions and reports:

- native/token F1: 55.92%, up 9.87 points from v12;
- semantic F1: 52.20%, up 10.06 points;
- gold-independent structure validity: 90.57%;
- evidence F1: 21.66%, up only 0.20 points;
- 17 paired improvements, one regression, and 141 unchanged rows.

All 17 improvements are gold-unanswerable questions whose unsupported
free-text answer became `unanswerable`. The remaining 15 structurally invalid
free-text outputs are all gold-unanswerable. Thirteen are associated with
verifier `status=error`; the other two contain exact grounded quotes that
directly support the question-candidate relation even though the benchmark
annotation is unanswerable.

The remaining class confusion, using the first canonical gold label only, is:

- gold `yes`: 25 predicted yes, 16 no, eight unanswerable;
- gold `no`: 21 predicted yes, 17 no, 12 unanswerable;
- gold `unanswerable`: four yes, four no, 37 unanswerable, 15 free text.

### Root cause

The v6 quote contract and structure metric work as designed. The remaining
failures have three causes:

1. Verifier output parsing fails on 24/159 rows. The error path immediately
   preserves the primary answer and does not retain the raw verifier response,
   so 13 unsupported free-text outputs survive and the parser failure cannot
   be audited.
2. The primary generator still confuses boolean polarity. The advisory
   verifier intentionally cannot flip a non-empty yes/no candidate because
   earlier authority-based versions introduced regressions.
3. The two accepted free-text/gold-unanswerable rows are not safely fixable by
   stricter lexical quote rules: their exact evidence quotes state the tested
   relation. Treat them as annotation/contract disagreement unless an
   independent human calibration changes the frozen label.

### Required remediation

- Add one repair attempt that is explicitly limited to JSON structure. The
  repair prompt must preserve the original verdict and quote and must not
  reconsider evidence or answer correctness.
- Persist the initial verifier response, repair response, repair status, and
  parser status for failures. Never silently fall back to token F1 or hide a
  verifier error.
- Keep the existing grounded-quote and question-relation checks after repair.
- Do not restore secondary authority over non-empty boolean candidates.
- Improve boolean polarity at the primary prompt/model boundary and evaluate it
  on a frozen calibration set rather than using gold-aware post-processing.
- Report annotation-disagreement rows separately from parser failures.

### Implemented in this remediation

- For the frozen typed subset, `yes`, `no`, and `unanswerable` are now all
  accepted canonical structures regardless of which typed gold value is
  present. Free-form spans remain invalid for this format gate.
- The answerability contract is now `qasper_answerability.v7`. Both boolean and
  free-text verifier schemas require an exact `evidence_quote`.
- A free-text `supported` verdict is rejected when its normalized quote is not
  present in retrieved evidence, fails candidate coverage, or lacks enough
  question-relation anchors. Boolean candidates remain advisory and cannot be
  flipped or erased by the secondary verifier.
- Traces distinguish quote grounding from question-relation support.
- Invalid verifier JSON receives at most one structure-only repair call. The
  prompt forbids reconsidering evidence or semantics, and traces retain the
  initial response, repair response, parser status, and repair status.

Artifact replay on the unchanged v12 predictions raised structure validity
from 62.89% to 80.50% (128/159). V13 subsequently reached 90.57%; neither
artifact closes answer quality.

### Still open

V13 improves answerability materially but still misses all closure thresholds:
structure is below 100%, semantic F1 is below 80%, and one paired regression
remains. JSON repair can remove the dominant structural error path, but primary
boolean capability and the two annotation disagreements require separate
evidence. `CONTRACT-002` remains P1.

### Closure evidence

Tests must prove that structure validity does not inspect the gold subtype,
unsupported quotes cannot confirm candidates, boolean advisory behavior is
unchanged, and explicit `unanswerable` remains stable.

The frozen subset must have 100% gold-independent structure validity, no net
verifier-induced paired regression, and semantic F1 at least 80%. If the
answer-quality target remains unreachable after evidence-quote validation,
the remaining limitation must be reported as model/retrieval capability rather
than repaired by gold-aware post-processing.

## PERF-001: Latency Evidence Must Remain Quality-Preserving

QASPER v13 median generation latency is 0.93 seconds with P95 1.45 seconds.
ALCE v9 median is 4.61 seconds with P95 5.34 seconds. Finance v12 median
generation latency is 14.44 seconds, P95 is 62.22 seconds, and two controller
routes hit an incorrectly effective 90-second budget.

Do not interpret text-only fallback, abstention, incomplete plans, or rejected
execution as a latency gain. Close this item only after the corrected focused
subsets pass quality gates and stay within the fixed simple and
multi-page/numeric latency budgets.

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
