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
├── residual-qasper-typed-v12-advisory-verifier-semantic-strict-single-a100/
│   └── outputs/20260724_170344_...-9914329
├── residual-finance-v11-required-hybrid-semantic-strict-single-a100/
│   └── outputs/20260724_171505_...-9914330
└── residual-alce-v9-safe-grounding-strict-single-a100/
    └── outputs/20260724_172225_...-9914331
```

Jobs `9914329`, `9914330`, and `9914331` all completed with exit code `0:0`.
The strict artifact validator confirmed 159/159 usable QASPER predictions,
80/80 FinanceBench predictions, and 60/60 ALCE predictions. All three runs had
zero route timeouts and zero execution-error rows.

The implementation before this remediation is commit `ccb6197`
(`fix: repair focused benchmark failure chains`). The new failing-first
protection tests are commits `e16a737`, `ebe9de8`, and `1c3e0f0`. The current
working implementation passes the protected unit and package-level gates, but
the P0/P1 items below remain open until replacement artifacts meet their
closure thresholds.

## Closed Problems Removed From The Active Register

The following items now have formal closure evidence and are no longer active
sections in this document:

- Per-job ports, single-GPU service co-location, and semantic evaluator alias
  startup. The latest jobs reached healthy local Qwen and retrieval services.
- RAGTruth global task contract. V17 retains 100% valid JSON, zero execution
  errors, 70.29% positive recall, 91.98% clean specificity, and 68.58% span F1.
- MMDocRAG element identity and structure expansion for the focused v6 gate.
- Semantic score integrity (`EVAL-003`). The live v12/v11/v9 artifacts contain
  no zero-claim perfect score, no scored execution-error row, and no semantic
  judge failure. Finance semantic F1 falling from the invalid 63.75% to 21% is
  a score-contract correction, not a system regression.
- Artifact completeness (`VALIDATION-002`). Formal wrappers now reject missing
  or unusable required rows, and the replacement ALCE artifact has 60/60 usable
  predictions.
- ALCE grounding authority (`ALCE-001`). V9 reaches 77.28% native score and
  95% citation F1 with 60/60 usable rows. Grounding changed none of the 60
  answers: 30 unsafe corrections, 21 inconsistent supported answers, and nine
  ungrounded answers remained telemetry instead of overwriting the candidate.
  Relative to complete v5, native score improves from 65.59% and citation F1
  from 80%.
- Duplicate-gain nDCG, parse-cache full-text preservation, shared index reuse,
  and timeout diagnostics retain their existing regression evidence.

RAGTruth Summary positive recall (37.04%) and Data2txt specificity (88.89%)
remain monitoring diagnostics, not blockers for the already passed global
contract.

## Open Problem Summary

| ID           | Priority | Area                                   | Current evidence                                                                                                                  | Completion gate                                                                                                                                       |
| ------------ | -------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| FINANCE-001  | P0       | Retrieval and hybrid eligibility       | V11 page hit 33.75%, all pages 15%, Candidate Recall@50 27.5%, Reranked Recall@10 17.5%; every controller route fell back to text | A hybrid-eligible frozen run reaches page hit >=70%, all pages >=35%, and no required-hybrid question is silently evaluated as text-only              |
| FINANCE-002  | P0       | Slot binding and calculation semantics | Native 0%; one wrong-page plan produced 23002% while all execution metrics reported success                                       | Required slots are semantically bound, plans cover every slot, native >=20%, all operands >=50%, conditional execution >=95%, unit accuracy >=98%     |
| CONTRACT-002 | P1       | QASPER answer and scoring contract     | V12 native 46.05%, semantic 42.14%, current structure metric 62.89%, evidence F1 21.46%                                           | Gold-independent structure validity 100%, no verifier-induced regression, semantic F1 >=80%, and class diagnostics close yes/no/unanswerable failures |
| PERF-001     | P1       | Quality-preserving latency             | No timeouts, but Finance quality is invalid and P95 rose to 12.67 seconds                                                         | Quality gates pass with zero required-row error; simple median increase <=20%, multipage/numeric <=50%, with P95 reported                             |
| EVAL-001     | P1       | Global release gate                    | Calibration and G-minus-B paired evidence remain incomplete                                                                       | Judge coverage >=99.5%, agreement >=90%, semantic gain >=8 points, paired CI lower bound >0                                                           |
| EVAL-002     | P2       | External evaluator                     | No fixed paper-grade external evaluator artifact                                                                                  | Frozen evaluator/provider contract and complete formal artifact                                                                                       |
| FORMAT-001   | P2       | Production formats                     | Loader smoke exists; preview/OCR/formula/chart E2E matrix remains incomplete                                                      | Required production-format matrix passes                                                                                                              |

Do not launch another full 3,540-prediction benchmark until `FINANCE-001`,
`FINANCE-002`, and `CONTRACT-002` pass their frozen focused subsets.

## FINANCE-001: The Focused Run Did Not Exercise Required Hybrid Evidence

### Evidence

Finance v11 reports:

- native numeric score: 0%;
- page hit: 33.75%;
- all-gold-pages hit: 15%;
- Candidate Recall@50: 27.5%;
- Reranked Recall@10: 17.5%;
- false abstention: 22.5%;
- median generation latency: 1.25 seconds;
- P95 generation latency: 12.67 seconds.

Page hit is unchanged from v10, while all-pages hit falls from 22.5%,
Candidate Recall@50 from 39.17%, and Reranked Recall@10 from 34.17%.

The planner identifies seven of the twenty examples as structured calculations
and initially selects `hybrid`. The focused wrapper, however, configures File
Collection retrieval mode as `text`; every prediction records
`available_modalities=[]`. Cost-aware routing therefore normalizes all hybrid
and page-image decisions to `doc_text`. `text_rag`, `controller_auto`, and
`crag_guarded` consequently produce the same retrieval failures and answers.

### Root cause

The production fallback is correct when visual and element backends are truly
unavailable. The validation design is not: a text-only focused wrapper cannot
prove that required-hybrid preservation, page retrieval, element retrieval, or
cross-modal fusion works.

The trace currently labels this condition `normalized_from_hybrid`, which
looks like an ordinary cost decision rather than a missing validation
capability. This allowed a run that never exercised hybrid evidence to be
interpreted as a required-hybrid test.

Retrieval quality also regressed before calculation. The correct gold-like
items are absent from the candidate set for several examples, and the top
reranked set loses additional recall. Calculation changes cannot repair this
boundary.

### Required remediation

- Record a distinct `required_hybrid_unavailable` route decision and an
  explicit eligibility field whenever a structured calculation requires
  hybrid evidence but no complementary modality has usable candidates.
- Formal Finance hybrid validation must refuse to close the gate when that
  eligibility field is false.
- Re-run the frozen subset through the full-system page/element-capable
  runtime, not `text_route_rerun.sbatch`.
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

### Still open

The replacement Finance run has not completed on a manifest whose controller
and CRAG routes configure `colqwen` plus `local_qwen3_vl`. Page hit,
all-gold-pages hit, candidate recall, reranked recall, and false abstention
therefore have no new evidence. This item remains P0 even though a text-only
false closure is now prevented.

### Closure evidence

Every structured numeric example must either execute a genuinely available
hybrid route or explicitly fail hybrid eligibility. On eligible rows, page hit
must reach 70%, all-gold-pages hit 35%, and Reranked Recall@10 must not regress
from the last valid pre-v11 focused baseline. Text-only fallback rows must be
reported separately and cannot close this item.

## FINANCE-002: Slot And Program Verification Accept Semantically Wrong Inputs

### Evidence

Finance v11 exposes more trace data but still has 0% native numeric score.
Aggregate all-operands and execution accuracy both report 25%, yet their
coverage is only 30%; operand accuracy covers only 7.5% of predictions.

For the three-year Nike cost-of-goods-sold percentage question:

- QueryPlan correctly creates required 2016, 2017, and 2018 slots.
- The same unrelated evidence can fill several slots merely because it
  contains the requested years and some numbers.
- The calculation plan contains only 2017 and 2018 operands.
- One operand has scale `thousand`; the other has no scale.
- The executor averages the scaled values and returns `23002%`.
- Slot coverage, operand accuracy, operator accuracy, program accuracy,
  execution accuracy, and unit accuracy are all recorded as 1.

The question actually asks for the average of annual
`cost of goods sold / revenue` percentages. The current QueryPlan creates only
cost-of-goods-sold slots, and the numeric adapter averages raw values instead
of constructing the two operands and ratio step for each year.

The PepsiCo capital-spending alias now activates the numeric executor, but
retrieval selects pages 52 and 114 instead of gold page 63 and returns
`$4.5 billion` instead of `$4.6 billion`. This confirms that trace activation
is fixed while semantic evidence correctness is not.

### Root cause

There are four independent validation gaps:

1. Slot scoring accepts a period match plus any numeric value even when no
   metric alias matches the evidence.
2. Calculation verification checks only the operands present in the generated
   plan. It does not compare the plan against every required QueryPlan slot.
3. Compatibility checks ignore missing dimensions when a peer operand has an
   explicit scale, unit, or currency.
4. Stage metrics equate internally reproducible execution with a complete and
   semantically valid program. Coverage is reported separately but the headline
   average can still look successful.

### Required remediation

- A numeric slot with a metric must require a supported canonical alias, the
  requested period, a traceable evidence identity, and a numeric value.
- Build explicit numerator and denominator slots for multi-period
  “metric as percentage of metric” questions.
- Pass the bound QueryPlan into the numeric adapter. Verification must match
  each required slot to a distinct plan operand with compatible period,
  metric, and allowed evidence identity.
- Reject a plan when any required slot is missing, even when every operand
  present in the incomplete plan is traceable.
- Treat explicit-versus-missing scale/unit/currency as incompatible for
  arithmetic that requires comparable dimensions.
- `all_operands_bound` must require a valid complete plan; failed plan
  verification cannot receive full operand credit.
- Keep arithmetic execution separate from answer correctness. Native numeric
  match remains the final answer-quality authority.

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

### Still open

Local regression fixtures now reject the exact incomplete/mixed-scale program
and reproduce the correct multi-period ratio plan. No replacement frozen
artifact has yet shown native numeric >=20%, all-operands >=50%, or the
conditional execution and unit thresholds. Retrieval remains an upstream
blocker for those gates.

### Closure evidence

Regression fixtures must cover the exact 23002% failure, missing periods,
unrelated year-number tables, multi-period percentage-of-revenue programs,
dimension mismatch, incorrect evidence IDs, and stage-metric coverage.

Every numeric example must emit a trace. All required slots must be represented
in the plan and covered by final citations. The frozen eligible subset must
reach all-operands 50%, native numeric 20%, false abstention at most 15%, and,
conditional on a valid complete plan, execution accuracy 95% and unit accuracy
98%.

## CONTRACT-002: QASPER Primary Answers And Structure Metrics Remain Invalid

### Evidence

QASPER v12 improves over verifier-authority v11:

- native/token F1: 37.88% to 46.05%;
- semantic F1: 28.30% to 42.14%;
- structure validity: 35.22% to 62.89%;
- evidence F1: unchanged at 21.46%.

Paired v11-to-v12 comparison has 26 exact improvements and four regressions.
Relative to v9, native and semantic F1 improve only 0.63 points and structure
validity is unchanged.

The advisory verifier behaves as intended:

- 52 `insufficient_evidence` candidates are preserved; 25 are exact answers.
- The one conflicting boolean verdict is preserved and the primary answer is
  correct.
- Nine unsupported free-form candidates become `unanswerable`; all nine match
  the frozen gold.

The remaining primary-answer confusion is large:

- gold `no`: 17/50 exact, 21 predicted `yes`, 12 `unanswerable`;
- gold `yes`: 25/49 exact, 16 predicted `no`, eight `unanswerable`;
- gold `unanswerable`: 21/60 exact, 39 unsupported concrete answers.

The pre-remediation `qasper_structure_valid` implementation uses the gold answer
category. It rejects `unanswerable` for a gold boolean and rejects `yes/no` for
a gold-unanswerable example. This measures type correctness, not response
structure, and makes the 100% structure gate incompatible with the requirement
that runtime behavior cannot derive the gold type.

### Root cause

Verifier authority is no longer the dominant problem. The primary generator
still confuses polarity and converts related paper facts into answers to
unanswered questions.

The secondary verifier returns a bare verdict. A `supported` decision has no
machine-checkable evidence quote, so a hallucinated relation can be accepted
when the paper contains the candidate phrase in unrelated context.

The structure metric conflates format validity with knowledge of the gold
answer subtype. This obscures whether a failure is malformed output or an
incorrect but well-formed answer.

### Required remediation

- Define structure validity independently of the gold subtype. For the frozen
  typed subset, `yes`, `no`, and `unanswerable` are all canonical structures;
  a rationale or arbitrary span is not.
- Keep correctness in QASPER F1 and semantic F1 rather than hiding it in the
  format metric.
- Require the answerability verifier to return an evidence quote. A supported
  verdict without a normalized quote found in the supplied evidence must be
  treated as unsupported telemetry.
- The quote must support the question-candidate relation, not merely contain a
  candidate token. Keep verifier action and quote-validity diagnostics.
- Do not restore secondary authority over non-empty boolean candidates.
- Report yes, no, and unanswerable confusion separately.

### Implemented in this remediation

- For the frozen typed subset, `yes`, `no`, and `unanswerable` are now all
  accepted canonical structures regardless of which typed gold value is
  present. Free-form spans remain invalid for this format gate.
- The answerability contract is now `qasper_answerability.v6`. Both boolean and
  free-text verifier schemas require an exact `evidence_quote`.
- A free-text `supported` verdict is rejected when its normalized quote is not
  present in retrieved evidence, fails candidate coverage, or lacks enough
  question-relation anchors. Boolean candidates remain advisory and cannot be
  flipped or erased by the secondary verifier.
- Traces distinguish quote grounding from question-relation support.

Artifact replay on the unchanged v12 predictions raises structure validity
from 62.89% to 80.50% (128/159), not 100%. The remaining 31 predictions are
free-form answers on the typed subset, so this metric correction does not close
answer quality.

### Still open

No v6 frozen QASPER run exists yet. It must show whether evidence-quote
validation removes unsupported free-form answers without inducing paired
regressions. The v12 semantic F1 of 42.14% remains far below the 80% closure
threshold, so `CONTRACT-002` remains open.

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

The latest runs have zero timeout and execution-error rows. QASPER median total
latency is 1.01 seconds with P95 1.42 seconds. ALCE median is 4.61 seconds with
P95 5.34 seconds. Finance median generation latency is 1.25 seconds, but P95 is
12.67 seconds and answer quality remains invalid.

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
