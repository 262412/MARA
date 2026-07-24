# Residual Risks And Open Problems

Last updated: 2026-07-24.

This is the canonical register of unresolved MARA benchmark and engineering
risks. It contains only problems that still require implementation or formal
closure evidence. A smoke result does not close a formal release gate, and an
improved metric implementation is not counted as a model or system-quality
gain.

## Current Evidence Snapshot

The frozen full-system baseline remains:

```text
/mnt/scratch/users/tbczhang/outputs/MARA/
final_thesis_benchmark_statistical_20260720_repair_g_fullsystem
```

The latest focused validation artifacts are:

```text
04_residual_validation/
├── finance-v7-job-scoped-ports/outputs/
│   └── 20260724_111238_residual-finance-v7-job-scoped-ports-n20-9912535
├── mmdocrag-element-v6-structure-gpu-colocate/outputs/
│   └── 20260724_104312_residual-mmdocrag-element-v6-structure-gpu-colocate-n20-9912524
├── alce-v5-gpu-colocate/outputs/
│   └── 20260724_041652_residual-alce-controller-v5-gpu-colocate-n20-9912111
├── qasper-typed-v9-answerability-v2-job-scoped-ports/outputs/
│   └── 20260724_105927_residual-qasper-typed-v9-answerability-v2-job-scoped-ports-n159-9912551
└── ragtruth-v15-calibrated-job-scoped-ports/outputs/
    └── 20260724_110359_residual-ragtruth-v15-calibrated-job-scoped-ports-n300-9912537

offline-replays-20260724/
├── 20260724_130917_finance-v7-current-code-replay
└── 20260724_131028_qasper-v9-current-code-replay

post-remediation-20260724/
├── 20260724_133007_residual-qasper-typed-v10-answerability-v3-full-chunk-compatible-fallback-9913039
├── 20260724_134654_residual-ragtruth-v16-remediation-compatible-fallback-9913040
└── 20260724_135543_residual-finance-v8-remediation-compatible-fallback-9913041
```

Verified focused results:

- Jobs `9912535`, `9912537`, and `9912551` completed with exit `0:0`.
  Finance has 79/80 usable predictions because one required text-route row
  timed out; RAGTruth has 300/300 usable and QASPER has 159/159 usable.
- The three jobs used distinct LLM/retrieval port pairs
  `22535/42535`, `22537/42537`, and `22551/42551`. Their logs have no address
  collision, disconnected peer, connection refusal, or traceback. The old
  Slurm co-location problem is therefore closed and is no longer an open item.
- MMDocRAG element retrieval reaches element hit 45%, page hit 80%,
  all-gold-pages hit 30%, and token F1 13.69%. The v6 artifact has 20/20 usable
  predictions, 121/126 evidence items retain a parent ID, all 126 retain a
  normalized hash, and 18/20 predictions run structure expansion at reported
  coverage 1.0. The other two report coverage 0 and correctly disable
  expansion. The old element retrieval and structure-metadata problems remain
  closed.
- RAGTruth v15 has 100% valid JSON, zero execution errors, 70.29% positive
  recall, 83.95% clean specificity, and 64.51% span F1. It passes every
  contract gate except specificity. Its improvement over v13 is a calibrated
  precision/specificity shift, not complete closure.
- QASPER v9 has token/native F1 45.42%, deterministic semantic F1 41.51%, and
  structure validity 62.89%. Boolean semantic accuracy is 45.45%;
  unanswerable accuracy is 35%. Evidence F1 is unchanged at 42.25% across v6,
  v8, and v9, so the gain is answerability/finalization behavior rather than
  retrieval improvement.
- Finance v7 has diagnostic token F1 19.18%, overall page hit 33.75%, quality
  route page hit 45%, quality all-gold-pages hit 30%, and one 180-second
  timeout. No prediction contains a Finance execution trace. The reported
  quality native score of 20% is inflated by first-number matches on
  descriptive answers and is not valid closure evidence.
- Finance supported-answer false abstention is 5% on controller/CRAG routes,
  below the 15% gate. One capital-expenditure example nevertheless switches to
  page generation without a VLM on both routes, so capability gating remains
  open.
- ALCE has native score 65.59%, citation F1 80%, and false abstention 0%.
- Semantic-judge coverage remains 0 for Finance, MMDocRAG, and ALCE because
  the evaluator was disabled. Their partially populated semantic fields are
  diagnostic fallbacks and cannot close semantic gates.
- The duplicate-gain nDCG defect is closed. Unit coverage now permits gain only
  for the first hit on each unique gold identity. Replaying the focused
  artifacts measured 59 Finance, 20 MMDocRAG element, 60 ALCE, and 900
  RAGTruth traces with zero values outside `[0, 1]`; every measured maximum is
  1.0.
- Re-scoring Finance v7 with the corrected numeric metric preserves historical
  token F1 at 19.18% but lowers native score from 15% to 6.25% and quality
  native score from 20% to 8.33%. This is removal of year-as-answer false
  positives, not a system regression. Twenty numeric rows are now measured and
  all are correctly attributed to `retrieval_or_plan`; the old predictions
  contain no executor trace, so they cannot validate the new execution path.
- Re-scoring QASPER v9 shows that 82 rows in the old compact artifact cannot be
  assigned a full-chunk span stage: 77 are not applicable and 82 are
  unavailable, with only six preview hits. The legacy text system persisted
  only a 400-character preview. New predictions now expose complete retrieved
  chunk text to scoring before compact artifact projection, but this
  observability repair requires a new focused artifact.

Current local implementation verification:

- `benchmark/tests`: 399 passed.
- `ktem` DocQA/MARA tests: 1,286 passed.
- `kotaemon` tests: 350 passed and eight skipped.
- The focused RAGTruth split suite has 27 passing tests.
- The code-hygiene ratchet passes without refreshing the baseline.

The post-remediation focused validation chain reached a terminal state:

```text
9913039 QASPER v10  COMPLETED 0:0; 159/159 usable
   └─ 9913040 RAGTruth v16  COMPLETED 0:0; 300/300 usable
      └─ 9913041 Finance v8  COMPLETED 0:0; 80/80 usable
         └─ 9913065 Finance v9 + semantic judge  FAILED 1:0 before benchmark
            └─ 9913066 ALCE v7 + grounding + semantic judge  FAILED 1:0 before benchmark
```

The first three jobs used the same frozen manifests, limits, and sample seed as
their predecessors. Finance v9 and ALCE v7 passed LLM and retrieval health
checks but received `MARA_SEMANTIC_EVALUATOR=local`; the benchmark accepts only
`off`, `local_qwen3_8b`, or a Python path. Both jobs therefore failed while
constructing the semantic judge and produced no predictions. This is a
submission-contract failure, not a model, GPU, or retrieval failure.

The completed artifacts establish the following new evidence:

- QASPER v10 regresses from v9: native/token F1 falls from 45.42% to 41.52%,
  deterministic semantic F1 from 41.51% to 34.59%, structure validity from
  62.89% to 47.17%, and evidence F1 from 42.25% to 21.46%. Of 28 boolean rows
  changed to `insufficient_evidence`, 18 still have a gold-span hit. For the 50
  gold-`no` rows, only four finish as `no`, 15 as `yes`, and 31 as
  `unanswerable`.
- RAGTruth v16 retains 100% JSON validity and improves positive recall from
  70.29% to 73.19%, but clean specificity falls from 83.95% to 82.72% and span
  F1 from 64.51% to 63.78%. It recovers 11 old false negatives, regresses seven
  old true positives, introduces three new false positives, and resolves one
  old false positive.
- Finance v8 completes 80/80 rows with no timeout, but token F1 falls from
  19.18% to 12.45%, corrected native score is 0%, page hit and all-gold-pages
  hit are both 0%, all-operands bound is 0%, and supported-answer false
  abstention rises to 37.5%. All 348 evidence items lack page, element, table,
  row, and column identity and retain only source-level provenance. Eighteen
  calculation traces are now observable: nine fail with `missing_operands`
  and nine with `unsupported_formula`.
- The 549-page PepsiCo row completes. Its text route takes 14.26 seconds
  including amortized preparation, while subsequent controller/CRAG routes
  reuse the shared index in under one second. This validates the cache and
  timeout instrumentation, but not answer quality: all three evidence routes
  abstain.

A post-fix focused validation chain was submitted after the local gates
passed:

```text
9914072 QASPER v11 + answerability v4 + semantic judge
   └─ 9914073 RAGTruth v17 + source/support repair
      └─ 9914074 Finance v10 + parse-cache/execution repair + semantic judge
         └─ 9914075 ALCE v8 + grounding + semantic judge
```

The chain uses one A100 with the Qwen and retrieval services co-located,
`MARA_QWEN3_8B_GPU_MEMORY_UTILIZATION=0.65`, 8 CPUs, 120 GB host memory, and
isolated output/runtime directories. `afterany` dependencies serialize the
jobs without suppressing later dataset validation when an earlier job fails.
At submission, `9914072` started on `gpu07`; its preflight normalized `local`
to `local_qwen3_8b` before either service started. Do not infer metric closure
until all four artifacts are complete and analyzed.

Do not launch another full 3,540-prediction run until the P0/P1 frozen subsets
below pass. Use regression tests, artifact replay, and focused route matrices
first.

## Open Problem Summary

| ID             | Priority | Area                       | Current status                                                                                                   | Completion gate                                                                       |
| -------------- | -------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| VALIDATION-001 | P0       | Semantic evaluator launch  | Alias normalization and fail-fast import validation are implemented locally; replacement jobs are not complete   | Invalid values fail in preflight; canonical local evaluator completes with coverage   |
| CONTRACT-001   | P0       | RAGTruth                   | Source trimming and support policy are repaired locally; fixed-output v16 replay passes all quality thresholds   | JSON >=99%, recall >=70%, specificity >=90%, span F1 >=60% on a new formal run        |
| FINANCE-001    | P0       | Finance identity/execution | Parse-cache truncation and direct-value execution are repaired locally; no post-fix runtime artifact exists      | No non-numeric activation; page >=70%, operands >=50%, native numeric >=20%           |
| CONTRACT-002   | P1       | QASPER                     | v4 separates evidence sufficiency from evidence-derived polarity; no post-fix focused artifact exists            | Structure 100%, semantic F1 >=80%, no unanswerable-to-no conversion                   |
| CONTROL-001    | P1       | Route capability/risk      | Direct monetary questions now expose structured risk and select hybrid locally; runtime false abstention is open | No unavailable route selection; supported false abstention <=15%                      |
| PERF-001       | P1       | Latency/timeouts           | v8 has zero timeouts and cache reuse, but early abstention invalidates quality-preserving latency closure        | Zero required-row timeouts and latency budgets pass without quality regression        |
| ALCE-001       | P1       | ALCE answer/citation       | Grounding implementation remains unvalidated because v7 produced no predictions                                  | Native >=75%, citation F1 >=93%, no semantic regression                               |
| EVAL-001       | P1       | Global release gate        | Judge launch failed and the frozen 200-row human calibration is still absent                                     | Judge coverage >=99.5%, agreement >=90%, semantic delta >=8 pp with CI lower bound >0 |
| EVAL-002       | P2       | External evaluator         | No fixed paper-grade external evaluator run                                                                      | Frozen evaluator contract and completed formal artifact                               |
| FORMAT-001     | P2       | Production formats         | Basic loader smoke passes; preview/OCR/formula/chart E2E coverage is incomplete                                  | Required production-format matrix passes                                              |

## CONTRACT-001: RAGTruth Over-Detects Supported Claims

### What is fixed

- The dedicated task prompt contains `source_info + response`, uses separate
  budgets, and never enters generic answer generation.
- All routes use strict `{"hallucination list": [...]}` JSON Schema output.
- Structure-only repair is limited to one attempt and cannot rewrite spans.
- Mapping-shaped sources are now flattened to their textual leaves, and
  high-coverage lexical support checks reject numeric, negation, and
  directional-relation conflicts.
- Ordinary unsupported claims now require detector consensus. Deterministic
  single-path promotion is limited to explicit contradictions or strong
  structured-field mismatches, with data-to-text handled separately.
- The v15 text-route run has 100% JSON validity, zero execution errors, 70.29%
  positive recall, 83.95% clean specificity, and 64.51% span F1. JSON, recall,
  and span F1 gates now pass.
- The local detector now persists candidate, verifier, consensus, heuristic,
  support-filter, and emitted claim indices together with their spans.
  Support filtering checks relation/superlative conflicts and known advice
  paraphrases, while structured data-to-text comparison covers booleans,
  unknown values, reservations, outdoor seating, hours, and review counts.
- Source-budget enforcement now ranks response-relevant sentences instead of
  keeping only the leading text. Data-to-text sources remain valid Python
  mappings after trimming, so attributes and review facts are still available
  to deterministic support checks.
- Structured comparison evaluates every mentioned field in a compound claim.
  Missing fields remain unknown rather than becoming contradictions. Supported
  response headings, question restatements, source-limit statements, close
  paraphrases, and `each`/`every` equivalents no longer create false positives.

### Root cause

RAGTruth v16 confirms that the remaining error is not one global threshold
problem:

- QA has 12 false positives and six false negatives. False positives still mix
  heuristic-only novelty decisions with candidate/verifier agreement.
- Summary has 11 false positives; every one has candidate/verifier consensus.
  The support filter still misses entailed paraphrases after both detectors
  select the same response claim. Summary also retains 17 false negatives,
  mostly detector disagreement or unmatched claim indices.
- Data-to-text improves positive recall from 78.48% to 82.28%, but specificity
  falls from 91.67% to 86.11%. Attribute heuristics promote supported Wi-Fi,
  hours, seating, reservation, and ambience statements as hallucinations.
- Eleven positive examples are fully suppressed by the support filter,
  including seven data-to-text, two QA, and two Summary examples.
- Pairing v15 and v16 shows the net trade: 11 false negatives recovered, seven
  true positives lost, three new false positives introduced, and only one old
  false positive resolved.

### Implemented remediation and remaining validation

Source entailment, structured-field conflict, and task-specific promotion are
now separate decisions. Direct structured support takes precedence over
heuristic novelty, while numeric, negation, directional-relation, and
qualifier conflicts still block lexical support.

A conservative replay over the frozen v16 artifact held both model detector
outputs fixed and changed only deterministic source construction and support
filtering. It measures 70.29% positive recall, 90.74% clean specificity, and
67.92% span F1, passing all three quality thresholds. This is causal evidence
for the code repair, but not formal closure because it reuses v16 model
outputs. Issue one untouched 300-row validation without changing thresholds.

### Closure evidence

JSON validity must remain at least 99%, execution errors must remain zero,
positive recall must be at least 70%, clean specificity at least 90%, and span
F1 at least 60% on the frozen formal set.

## FINANCE-001: Intent, Operand Identity, And Result Validity Were Conflated

### What is fixed

- The deterministic executor uses `Decimal`, an operator allowlist, evidence
  IDs, and dimension checks.
- Untraceable operands, unit/scale/currency mismatches, zero division, and
  invalid plans are rejected.
- Failure-stage and conditional executor metrics are exposed.
- Causal/descriptive markers now take precedence over numeric surface terms.
  Those questions are planned as long-form questions and cannot activate the
  Finance numeric adapter.
- Generic operands bind distinct canonical evidence greedily instead of
  satisfying multiple required slots with the same evidence.
- Numeric/Finance finalization collapses short decorated repetitions such as
  `$38$38`, while date strings keep their original behavior.
- Regression tests cover the exact causal SG&A example, distinct operand
  binding, and decorated numeric repetition.
- Finance v7 confirms the SG&A causal question is planned as `long_form` and
  does not activate the numeric adapter.
- Finance applicability now reads the nested QueryPlan domain and answer type.
  Numeric plans that lack evidence, operands, or a supported formula emit an
  auditable failed trace instead of silently returning `None`.
- Query planning creates fiscal-year-aware, metric-specific slots and targeted
  subqueries. The shared adapter now supports free cash flow, multi-period and
  percentage averages, average-inventory turnover, and direct values without
  reusing one cell for distinct operands.
- Numeric native scoring skips likely years when an answer-shaped non-year
  number exists. The current-code replay preserves token F1 while exposing the
  old native-score inflation.

### Root cause

Finance v8 moves the failure boundary forward and exposes the remaining root
cause:

1. Retrieval often finds answer-bearing table text, but all 348 evidence items
   have empty page, element, table, row, and column identity. Every provenance
   back-reference ends at `#source`.
2. QueryPlan reports slot coverage 1.0 by attaching the same document chunks
   to period-specific slots. Without cell identity, the executor cannot bind a
   value, period, metric, unit, or scale to an operand.
3. Eighteen numeric attempts emit an auditable trace, but nine fail with
   `missing_operands` and nine with `unsupported_formula`; no plan executes.
4. The controller receives `structured_calculation=false` even for the
   PepsiCo capital-expenditure question. Numeric intent is identified only
   after route choice, so controller and CRAG remain on `doc_text`.
5. The verifier converts all 21 applicable numeric route rows and nine
   extractive rows into supported-answer false abstentions. The overall rate
   is 37.5%, and each quality route reaches 50%.
6. Page hit and all-gold-pages hit are 0 because source-level evidence cannot
   be projected back to pages, even when answer-bearing text was retrieved.
7. A fresh-cache diagnostic isolates the identity loss before retrieval.
   `PDFReader` returns all 549 PepsiCo pages with correct page metadata and the
   capital-spending row on page 63. The parse cache then wrapped each native
   LlamaIndex `Document` as `Document(document)`, which stored the object's
   roughly 400-character `Doc ID: ... Text: ...` preview instead of its full
   text and metadata. This explains both the page-hit collapse and the missing
   operands in v8.

### Implemented remediation and remaining validation

Failed traces, formula selection, corrected native scoring, visual-intent
classification, shared index identity, and timeout instrumentation are
implemented. Native LlamaIndex documents are now copied into the parse cache
using full text, original document ID, and metadata. Page-scoped chunks without
a parser element ID receive a stable chunk-level element ID instead of losing
identity. A regression fixture verifies that a page-63, greater-than-400-byte
document survives cache storage without the `Doc ID:` preview prefix.

Direct monetary and value questions now bind one period-specific operand,
preserve the requested answer scale, and render an exact evidence-bound result.
The PepsiCo capital-spending regression returns `$4.625 billion` with a valid
trace and citation. Query risk extraction recognizes amount/value and
financial-statement terms before route scoring, so this question selects
hybrid rather than `doc_text` in local controller tests.

The focused route matrix must verify that every numeric attempt emits a trace,
no descriptive question activates the executor, page/cell provenance survives
projection, and a failed calculation does not overwrite a separately supported
extractive answer.

### Closure evidence

No causal/descriptive example may activate the numeric executor. Report raw
coverage next to every conditional metric. Page hit must reach 70%,
all-gold-pages hit 35%, all operands bound 50%, and native numeric score 20%.
When all operands are validly bound, execution accuracy must be at least 95%
and unit accuracy at least 98%.

## CONTRACT-002: QASPER Lacks An Evidence-Sufficiency Decision

### What is fixed

- Conversion preserves `boolean`, `unanswerable`, and `free_text`.
- Boolean aliases normalize to `yes/no`; explicit insufficient-evidence wording
  normalizes to `unanswerable`.
- The current route has no context overflow, timeout, or execution error.
- Runtime requests now use the dataset contract `qasper_qa` instead of the
  gold-derived answer category.
- A separate fixed-schema evidence verifier receives only the question,
  retrieved evidence, and candidate answer and emits `supported` or
  `unsupported`. Unsupported candidates finalize as `unanswerable` without
  consulting the gold type.
- The verifier decision and selected evidence IDs are retained in the trace,
  with unit and integration coverage for supported and unsupported cases.
- The v2 verifier no longer applies ordinary claim-support classification to
  `yes/no/true/false` candidates. Those candidates already encode the polarity
  chosen by the evidence-grounded answer generation call; treating the word
  `no` as a standalone claim caused systematic false rejection.
- QASPER v9 restores the v6 boolean ceiling and completes 159/159 rows without
  timeout.
- The local v3 contract replaces that unconditional bypass with a separate
  fixed-schema, polarity-independent decision: whether the selected evidence
  resolves the yes/no question. It never asks the verifier to validate the
  generated `yes` or `no` token itself and never reads the gold answer type.
- The local v4 contract requires the verifier to emit
  `yes/no/insufficient_evidence`. The final boolean answer comes from the
  evidence verdict, not from the candidate token, which separates polarity
  determination from evidence sufficiency.
- The legacy text route now exposes full retrieved chunk text to diagnostics;
  default compact reports still bound each text field to the artifact limit.

### Root cause

QASPER v10 demonstrates two separate failures:

- The v3 verifier changes 28 boolean rows to `insufficient_evidence`; 18 of
  those rows still contain a gold-span hit. It improves only three
  unanswerable rows, so structure validity loses a net 25 rows.
- Polarity generation remains biased toward `yes`. Of 50 gold-`no` rows, only
  four finish as `no`, 15 finish as `yes`, and 31 as `unanswerable`.
- Boolean semantic accuracy is 31.31% and unanswerable accuracy is 40%.
  Answerability cannot compensate for incorrect polarity.
- Full-chunk diagnostics show 91.46% gold-span hit overall, while evidence F1
  is 21.46%. The remaining evidence problem is selection precision and evidence
  identity alignment, not broad document recall alone.
- Negative questions that require paper-wide absence are fragile: top-k
  evidence cannot prove a negative merely because it does not mention a
  baseline, comparison, or property.

### Implemented remediation and remaining validation

The v4 implementation revises the verdict policy. Explicit evidence resolving
either polarity produces that evidence-derived boolean; unresolved evidence
becomes `unanswerable`. The verifier never reads the gold answer type. Formal
validation must still establish whether paper-wide negative questions need a
bounded full-document scan in addition to selected evidence.

### Closure evidence

Applicable structure validity must be 100%, no unsupported answer may be
coerced from the gold type, and semantic F1 must be at least 80% on the frozen
typed set.

## CONTROL-001: Route Selection Does Not Fully Respect Backend Capability

### What is fixed

Focused Finance, MMDocRAG, and ALCE runs bring supported-answer false
abstention below the 15% gate.

Non-visual auto/hybrid recovery now removes a pure page-generation candidate
when no visual generator is available, while retaining text/element evidence.
The controller request propagates the actual visual generator capability into
route-switch evaluation. Explicit visual requests intentionally retain the
existing evidence-only page fallback when no VLM is available; this is a
supported degraded mode, not an unavailable-backend invocation.

### Root cause

The frozen-run failure is earlier than the existing route-switch capability
filter. The PepsiCo capital-expenditure question says that the answer must come
from the statement of cash flows, but it does not ask to inspect an image,
figure, chart, or visual layout. Query classification nevertheless recorded
`visual_lookup`/visual intent. Auto and CRAG therefore treated the request as
an explicit visual question, preserved the evidence-only page fallback, and
both finished with `backend_unavailable` when no VLM was configured. The
filter was correct for a genuinely explicit visual request; the input
classification was wrong for this question.

The false-abstention gate also does not measure the opposite error:
unsupported-core-claim acceptance.

### Implemented remediation and remaining validation

Explicit visual intent now requires an actual image/figure/chart/diagram/slide
or layout reference. A statement, named table, section, page, or bare “shown”
is treated as a source constraint. Capability filtering remains active at
route selection and route switch, and non-empty rejected-route telemetry
records the unavailable route and reason. Regression tests cover the exact
PepsiCo wording and explicit visual controls.

Finance v8 confirms that unavailable visual generation is no longer selected;
all 40 controller/CRAG rows choose `doc_text` and no
`backend_unavailable` error occurs. It also exposes a routing-input gap:
numeric intent was absent from the controller features even when QueryPlan
later classified the question as numeric.

The controller request now derives structured risk from amount/value,
financial-statement, cash-flow, and balance-sheet terms before route scoring.
Direct monetary questions select structured hybrid evidence in local
regressions. Runtime false-abstention and unsupported-claim acceptance remain
open until the Finance focused matrix completes.

### Closure evidence

No route may invoke an unavailable required backend. Supported-answer false
abstention must remain at most 15% without increasing unsupported-core-claim
acceptance beyond its frozen calibration bound.

## PERF-001: One Long-Document Timeout Remains

### Root cause

Finance v8 confirms that repeated index preparation caused the prior long-row
timeout: the 549-page PepsiCo row now completes, its text route reports 14.26
seconds including amortized preparation, and subsequent controller/CRAG routes
reuse the shared index in under one second. The run has zero timeouts.

The remaining risk is measurement validity. Median total latency falls from
3.01 to 0.56 seconds and P95 from 71.45 to 3.77 seconds, but 30 quality-route
answers terminate as false abstentions. Faster early failure is not
quality-preserving latency improvement.

### Implemented remediation and remaining validation

The benchmark engine now records active-stage start/end events and exposes the
last active stage, partial timings, and document/index cache identity on a
timeout. Prepared file IDs are shared by content identity across route-family
engine instances. Report summaries include median, P95,
preparation-inclusive latency, and timeout counts. The DocQA request carries
one monotonic route deadline, and optional retrieval/execution stages consult
the remaining budget before proceeding.

The cache/timeout implementation is validated. Closure still requires the same
subset after Finance evidence and calculation repairs, with equivalent or
better answer quality and the current zero-timeout behavior.

### Closure evidence

Required rows must have zero timeouts. Simple-QA median latency increase must be
at most 20%; multi-page/numeric median increase must be at most 50%. Report P95
and timeout-inclusive quality.

## VALIDATION-001: Semantic Evaluator Submission Contract Is Not Enforced

### Root cause

The Slurm wrapper accepts any `MARA_SEMANTIC_EVALUATOR` string and forwards it
to the benchmark CLI only after both GPU services have started. Jobs `9913065`
and `9913066` used the intuitive alias `local`, while
`semantic_judge_backend()` accepts only `off`, `local_qwen3_8b`, or a Python
path. Both jobs consumed startup time and then failed before creating a single
prediction.

### Implemented remediation and remaining validation

- Both text and multimodal Slurm wrappers normalize
  `local`/`local_qwen3_8b` to the canonical identifier before runtime
  bootstrap and service startup.
- `off` aliases remain disabled; dotted Python evaluator paths are imported in
  preflight, so invalid values fail before model health checks.
- The benchmark semantic backend also accepts `local` as a direct alias without
  changing the reported canonical contract.
- Regression tests cover alias normalization, invalid paths, shell wiring, and
  direct benchmark alias handling.

Re-submit Finance and ALCE with new isolated output/runtime directories. The
failed directories remain infrastructure evidence, not benchmark artifacts.

### Closure evidence

An invalid evaluator value must exit before starting services. The canonical
local evaluator must complete the frozen focused subsets with judge coverage
reported explicitly; ALCE v7 must produce predictions and its grounding trace.

## ALCE-001: Answer And Citation Quality Remain Below Gate

### What is fixed

The focused route has zero false abstention and complete candidate/reranked
source recall.

Simple-fact evidence selection no longer blindly accepts candidate zero. It
recognizes the runtime `reranking_score`, rewards exact quoted phrases, full
dates, episode identifiers, proper-name phrases, and content anchors, then
uses constrained MMR. The behavior is limited to `simple_fact`; visual and
long-form ordering remains unchanged.

ALCE ASQA short answers now pass through a fixed-schema grounding verifier
after generation. It may preserve a supported answer, correct a competing
entity/date/list value, or return `unanswerable`; a correction is accepted only
when every answer token is traceable to the selected evidence item. Contract
status, evidence ID, answer-change flag, and latency are retained. QAMPARI is
excluded because its list contract is different.

On the old 20-example artifact, 16 examples have a literal gold span somewhere
in the selected evidence. The new selector proxy moves literal top-1 support
from 8/20 to 11/20: seven improve, while two apparent regressions are
misleading substring matches (`2004` in an unrelated merger sentence and
`108th season` rather than the requested drought). This proxy is useful causal
evidence but not a formal score.

### Root cause

Answer correctness is only 51.18%, native score is 65.59%, and citation F1 is
80%. All three tested routes produce effectively identical outputs, indicating
that current controller/CRAG choices add no useful evidence or citation
selection over text retrieval. The 60 predictions contain 21 full-span misses
and 12 citation misses. They contain no multi-citation answer at all, so
citation over-selection is not the current cause. Conversely, 21 answers have
the gold span in selected evidence but still score below full answer
correctness, and nine of those supported rows finalize as `unanswerable`.
Examples also select the wrong date, person, or episode despite having the
relevant source span. The remaining error is therefore split between retrieval
coverage, answer extraction/disambiguation, and citation identity projection.

### Implemented remediation and remaining validation

Full-chunk span-stage diagnostics, relevance-aware simple-fact lead selection,
and evidence-traceable short-answer grounding are implemented. Job `9913066`
did not enter the benchmark because of VALIDATION-001, so there is still no
runtime evidence that the grounding contract preserves supported answers,
corrects competing values, or binds citations to the selected evidence.
The remaining action is the frozen paired-subset run with the semantic judge
enabled after the submission contract is fixed.

Use that artifact to decide whether further implementation is justified:

1. If the gold span survives context selection but the grounded answer remains
   wrong, refine role/time/list constraint binding on the frozen calibration
   set rather than accepting a more weakly traceable answer.
2. If direct support still finalizes as `unanswerable`, classify whether the
   error came from evidence ordering or the grounding verdict before changing
   answerability.
3. If grounded answer support is correct but citation identity is wrong, bind the
   citation to the selected supporting sentence after claim aggregation.
   Preserve multiple citations only when one source is insufficient.

### Closure evidence

Native score must be at least 75%, citation F1 at least 93%, supported-answer
false abstention at most 15%, and paired semantic F1 must not significantly
regress.

## EVAL-001: The Global Release Gate Is Not Measurable Yet

The old frozen G-minus-B QA semantic improvement is only +0.38 percentage
points and its confidence interval crosses zero. The completed focused
Finance, MMDocRAG, and ALCE runs disabled the semantic judge, while the new
Finance v9 and ALCE v7 jobs failed before prediction because of
VALIDATION-001. They therefore provide zero judge coverage and cannot replace
the missing 200-example human-labeled calibration or a full B-through-G paired
ablation.

Required closure:

1. Freeze the 200-example semantic calibration set, local judge model, prompt,
   parser, temperature, and thresholds.
2. Reach at least 90% agreement and 99.5% parse coverage.
3. Re-run protected P0/P1 subsets with the evaluator enabled.
4. Rebuild B-through-G paired ablations only after dataset-specific gates pass.
5. Require G-minus-B QA semantic F1 of at least +8 points with paired 95% CI
   lower bound above zero and no protected-metric regression.

## EVAL-002: No Fixed Paper-Grade External Evaluator

The repository exposes evaluator interfaces and a local Qwen judge, but no
fixed external evaluator version/configuration has produced a complete formal
artifact.

Closure requires a frozen provider, model/version, prompt, parser, retry policy,
and cost budget, followed by calibration and formal runs that publish coverage,
failures, agreement, and the external primary metric. Until then, scores must
be described as local dataset-native, adapted, or diagnostic rather than
official leaderboard results.

## FORMAT-001: Production Format Robustness Is Incomplete

The current smoke establishes basic loader/index/query behavior for PDF, DOCX,
PPTX, XLSX, CSV, Markdown, and text. It does not cover preview, Office
conversion, OCR, complex slide layouts, spreadsheet formulas, charts,
citations, and answer generation as one production matrix.

Closure requires frozen PDF, DOCX, PPTX, XLSX, CSV, Markdown, text, OCR, and
chart fixtures, with separate loader, conversion, preview, indexing, retrieval,
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

- Keep only unresolved problems in this document.
- Remove an item only after its completion evidence exists.
- Add characterization or regression tests before changing Benchmark, DocQA,
  reporting, controller, or Slurm behavior.
- Do not refresh the code-hygiene baseline to make a gate pass.
- Link artifact directories rather than pasting large prediction payloads.
- Prefer artifact replay and focused frozen subsets before model reruns.
- Report raw metric coverage next to conditional success rates.
