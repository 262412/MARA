# Residual Risks And Open Problems

Last updated: 2026-07-25.

This is the canonical register of unresolved MARA benchmark and engineering
risks. It contains root causes, required corrections, and closure evidence.
A completed job, a valid JSON response, a retrieved page, or a reproducible
calculation does not by itself prove that the final answer is correct.

## Current Evidence And Release Verdict

The frozen full-system baseline remains:

```text
/mnt/scratch/users/tbczhang/outputs/MARA/
final_thesis_benchmark_statistical_20260720_repair_g_fullsystem
```

The latest completed focused artifacts are:

```text
04_residual_validation/
├── residual-qasper-typed-v16-answerability-v8-semantic-single-l40s/
│   └── 01_core_text/
│       └── 20260725_121032_...-9918145
└── residual-finance-v15-financial-elements-rendered-unit-l40s/
    └── outputs/
        └── 20260725_131322_...
```

Jobs `9918145` and `9918146` completed with exit code `0:0`. QASPER has
159/159 usable predictions; Finance has 80/80. The code used by these runs is
commit `8f01db5`.

The result is improved but not release-ready:

- QASPER v16: token/native F1 62.02%, semantic F1 58.49%, structure validity
  97.48%, evidence F1 21.66%, and verifier parser errors 0.
- Finance v15 quality routes: native numeric 13.33%, semantic F1 29.00%, token
  F1 14.68%, all-operands/execution 29.17%, unit accuracy 58.33%, and false
  abstention 18.75%.
- Finance v15 all routes: page hit 42.50%, all-gold-pages hit 32.50%,
  Candidate Recall@50 40.83%, and Reranked Recall@10 38.33%.
- Finance element-index availability is now 12/12 on the required hybrid
  subset, but only 4/12 indexed elements contain the answer-bearing table;
  8/12 point to a different page.

Do not launch another full 3,540-prediction benchmark until `IDENTITY-001`,
`EVAL-INVARIANT-001`, `FINANCE-001`, `FINANCE-002`, and `CONTRACT-002` pass
their frozen focused gates.

## Open Problem Summary

| ID                 | Priority | Area                            | Current evidence                                                                 | Completion gate                                                                       |
| ------------------ | -------- | ------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| IDENTITY-001       | P0       | Evidence and artifact identity  | Dataset, parser, index, reranker, and cell IDs are not unified                   | Zero reranker-lineage violations; strict and equivalent support traced                |
| EVAL-INVARIANT-001 | P0       | Metric contracts                | Candidate@50 and reranker pool semantics differ; question dimensions are ignored | Old metrics unchanged; additive invariant metrics measured on 100% of applicable rows |
| FINANCE-001        | P0       | Retrieval relevance             | Page 42.50%, all pages 32.50%; only 4/12 element records answer-bearing          | Page >=70%, all pages >=35%, required evidence survives reranking                     |
| FINANCE-002        | P0       | Table semantic binding          | Native 13.33%, operands 29.17%, unit 58.33%; wrong rows still bind               | Native >=20%, all operands >=50%, conditional execution >=95%, unit >=98%             |
| CONTRACT-002       | P1       | QASPER proposition and polarity | Parser errors are closed, but only 41/99 boolean rows are correct                | Structure 100%, semantic >=80%, proposition/polarity diagnostics pass                 |
| PERF-001           | P1       | Quality-preserving latency      | Finance quality gates fail despite zero timeout                                  | Quality gates pass and latency budgets remain satisfied                               |
| EVAL-001           | P1       | Global release gate             | Judge calibration and G-minus-B paired evidence incomplete                       | Agreement >=90%, coverage >=99.5%, gain >=8 points, CI lower bound >0                 |
| EVAL-002           | P2       | External evaluator              | No fixed paper-grade evaluator artifact                                          | Frozen evaluator contract and complete artifact                                       |
| FORMAT-001         | P2       | Production formats              | Preview/OCR/formula/chart E2E matrix incomplete                                  | Required production-format matrix passes                                              |

## IDENTITY-001: Evidence Has No End-To-End Canonical Identity

### Evidence

Finance v15 exposes two cases that the old exact-page metric cannot express:

1. A retrieved item can use a runtime UUID while the gold locator uses a
   filename stem such as `LOCKHEEDMARTIN_2021_10K`.
2. The same audited fact may appear in both an official statement and a
   selected-financial-data table. For `financebench_id_03031`, the system uses
   a semantically equivalent page 30 table while the dataset gold page is 68.
   Strict page hit correctly remains zero, even though the calculation is
   supported by an equivalent same-source table.

The existing table element is normally a whole-page or whole-table record.
There is no stable cell identity tying the metric row, period column, value,
source, and page together. The verifier can therefore prove only that a number
and metric words occur somewhere in the same large text item.

### Root cause

There are four incompatible identity domains:

- dataset identity: dataset example, source filename, annotated page, span;
- parser identity: file UUID, parser page index/label, element ID;
- retrieval identity: canonical/deduplicated evidence and source backrefs;
- calculation identity: evidence ID plus a numeric value, with no mandatory
  row/column locator.

Each stage reconstructs aliases independently. No shared identity contract
proves that a reranked item came from the canonical candidate pool or that a
calculation operand refers to a unique table cell.

Compact artifacts add a fifth identity break: stage metrics are calculated
from up to 80 candidates, but the previous compact writer retained only the
first 10 candidate records. A v15 replay therefore changes
`candidate_recall_at_50` from 0.5 to 0 on the three non-direct
`financebench_id_02024` routes. Those discarded candidate identities cannot be
recovered from the immutable compact artifact.

### Required remediation

- Define one additive evidence identity projection containing source aliases,
  dataset page, parser page, page aliases, canonical evidence ID, element ID,
  table ID, cell ID, row label/index, column label/index, period, and complete
  source backrefs.
- Preserve strict dataset locator metrics. Add a separate same-source semantic
  evidence-support metric; never convert an equivalent fact on a different
  page into a strict page hit.
- Compute reranker lineage from canonical evidence identity. Every reranked
  item must be traceable to the full reranker input pool.
- Carry cell identity into `calculation_plan.v1` operands and citations.
  Whole-table evidence remains the citation container, but verification must
  bind the operand to one row/column cell.
- Keep all new fields optional and additive so old artifacts remain readable.
- Compact artifacts must retain an identity-only projection of all 80
  reranker-input candidates and 30 reranked candidates. Large text and
  embeddings may be removed, but locator, canonical, element, cell, and
  provenance fields must remain replayable.

### Closure evidence

- Candidate pool, reranked list, selected evidence, plan operands, and final
  citations can be joined without text guessing.
- `reranker_lineage_coverage=1.0` and violation count is zero on every row with
  reranker traces.
- Strict page metrics are bit-for-bit unchanged on every newly written
  identity-complete artifact. The three known v15 compact rows remain marked
  non-replayable rather than silently rewritten.
- Equivalent fact support is reported independently with source and span
  evidence.
- Conflicting values, periods, units, or polarity never share a canonical
  fact/cell identity.

## EVAL-INVARIANT-001: Metric Denominators And Dimensions Are Not Stable

### Evidence

Finance v15 reports Candidate Recall@50 40.83% and Reranked Recall@10 38.33%.
An individual row can legitimately have Reranked Recall@10 greater than
Candidate Recall@50 because the reranker consumes up to 80 unique candidates,
not only the first 50. Treating that relationship as impossible would diagnose
valid behavior as corruption.

The semantic numeric evaluator also marks a correct answer such as
`$5,818 million` against gold `$5,818` as contradictory when the question
explicitly states that values are in USD millions. It compares dimensions only
inside prediction and gold strings and ignores the question contract.

Free-text semantic scoring can over-credit an incomplete answer when a judge
collapses multiple entity/value claims into one broad claim.

The v15 compact writer also makes metric denominators non-replayable: it stores
10 candidate records after calculating Candidate Recall@50 over as many as 50.
This is an artifact contract failure, not a retrieval-quality change.

### Root cause

- The metric name encodes a top-K cutoff but not the actual reranker input
  pool, and no lineage metric is emitted.
- Numeric contradiction detection treats a missing unit/scale as conflicting
  with an explicit one instead of inheriting an unambiguous question dimension.
- The free-text judge contract does not require atomic entity, relation, value,
  time, unit, scope, and polarity decomposition.

### Required remediation

- Keep `candidate_recall_at_50` and `reranked_recall_at_10` unchanged for
  historical comparability.
- Add `candidate_pool_recall_at_80`, `reranker_lineage_coverage`, violation
  count, and same-source `gold_evidence_support_recall`.
- Derive canonical identity before metric comparison and publish metric
  coverage/status with pool sizes.
- Persist all metric-input identities in compact artifacts; never recompute a
  top-K metric from a shorter stored prefix.
- In deterministic numeric scoring, inherit a missing currency, scale, or
  percent dimension from an unambiguous question. An explicit prediction/gold
  contradiction remains fatal.
- Upgrade the free-text judge prompt contract so every distinct entity/value
  proposition is counted separately and unsupported additions reduce
  precision.
- Judge errors remain `null`; do not silently fall back to token F1.

### Closure evidence

- Old `avg_f1`, native metrics, Candidate Recall@50, Reranked Recall@10, MRR,
  nDCG, and strict page metrics do not change on a newly produced compact
  artifact replay. Historical rows with already-discarded identities are
  explicitly reported as non-replayable.
- The new invariant metrics have 100% coverage wherever the required trace is
  present.
- Correct question-inherited dimensions score 1; explicit million/billion,
  currency, percent, direction, date, or polarity conflicts score 0.
- A frozen free-text calibration set demonstrates atomic-claim agreement and
  no incomplete-answer over-credit.

## FINANCE-001: Retrieval Finds Table-Like Elements But Often The Wrong Table

### Evidence

Finance v15 improved page hit from 33.75% to 42.50%, all-gold-pages hit from
23.75% to 32.50%, and Reranked Recall@10 from 25.83% to 38.33%. Candidate
Recall@50 is essentially flat at 40.83% versus 41.94%.

The newly persisted financial elements close the old availability failure:
all 12 required hybrid examples now have element-index records. They do not
close relevance: only 4/12 contain the answer-bearing table and 8/12 refer to
another page. Effective-route reporting and element coverage are now visible;
those old observability issues are closed.

### Root cause

- Element creation recognizes a table shape but does not rank whether the
  table satisfies the query's metric, period, and required operand slots.
- Whole-table embeddings blur row/column distinctions and favor nearby
  statement headings or visually similar financial pages.
- Slot restoration can only protect evidence that entered the canonical pool
  and was semantically bound to the correct slot.
- Strict gold-page metrics cannot distinguish a wrong table from an equivalent
  same-source duplicate without the additive support identity in
  `IDENTITY-001`.

### Required remediation

- Index table title, section, row labels, period headers, cells, and
  continuation identity as structured fields while keeping whole-table text.
- Score metric-row and period-column matches before generic semantic
  similarity. Protect the best distinct candidate for each required operand.
- Report retrieval stages by top-level and effective route, with strict locator
  recall and equivalent semantic support shown separately.
- Trace candidate loss at canonical pool, reranker, slot binding, MMR, and
  final context boundaries.
- Keep retrieval-free direct-answer rows out of retrieval averages.

### Closure evidence

Page hit reaches 70%, all-gold-pages hit reaches 35%, answer-bearing element
hit@10 reaches 30%, and required-slot evidence does not disappear after
reranking/MMR. Equivalent duplicate pages must improve the support metric, not
the strict locator metric.

## FINANCE-002: Numeric Values Are Not Bound To Table Semantics

### Evidence

Finance v15 improves quality native numeric score from 8.33% to 13.33%,
semantic F1 from 24.67% to 29.00%, all-operands/execution from 16.67% to
29.17%, slot coverage from 86.67% to 97.78%, and false abstention from 25% to
18.75%. Token F1 regresses from 16.02% to 14.68%, and unit accuracy remains
58.33%.

`financebench_id_00882` and the rendered scale of `03031` are fixed.
Remaining examples show the deeper defect:

- `03531` and `10285` bind a number from the wrong row/cell.
- `04854` has a requested period but can bind the result/distractor or the
  wrong capital-expenditure value in a multi-column table.
- `04302` and `10499` still produce no complete calculation plan.
- `04980` calculates a plausible value but remains native-incorrect, showing
  that arithmetic reproducibility is not answer correctness.

### Root cause

Numeric extraction is primarily prose-regex based. It flattens a financial
table into text and scans near a metric alias. In a table, the meaning of a
number is the intersection of a row label and column header; proximity in the
flattened text is not enough. The adapter subsequently selects an evidence item
containing the expected number, and the verifier checks the number and metric
against the entire item, so a wrong cell can pass.

### Required remediation

- Parse a deterministic financial table IR before numeric planning:
  `table -> headers -> metric rows -> typed cells`.
- A cell must carry source/page/table identity, row label/index, column
  label/index, period, Decimal value, unit, scale, and currency.
- Bind operands by metric aliases plus requested period, then value. Do not
  search the whole table for any occurrence of the expected value.
- Carry `cell_id`, row label, and column label into the plan. The verifier must
  reparse/reload that exact cell and reject a row, period, value, unit, scale,
  or currency mismatch.
- Use structured period values for working capital, free cash flow,
  multi-period averages, ratios, and changes. Prose extraction remains only a
  fallback when no table structure exists.
- Keep all arithmetic in `Decimal`, preserve the verified plan scale during
  rendering, and require citations for every operand.

### Closure evidence

Regression fixtures must cover multi-year headers, parenthesized negative
values, repeated equal values in different rows, same metric across periods,
wrong-row distractors, continuation tables, scale headers, and the exact
`$5,818 million` and `$3,215.4 million` outputs.

The frozen subset must reach native numeric 20%, all-operands 50%, false
abstention at most 15%, and, conditional on a complete valid plan, execution
accuracy 95% and unit accuracy 98%.

## CONTRACT-002: QASPER Boolean Semantics Remain Unstable

### Evidence

QASPER v16 closes the output-truncation failure:

- verifier parser errors fall from 24 to 0;
- token/native F1 rises from 55.41% to 62.02%;
- semantic F1 rises from 51.57% to 58.49%;
- structure validity rises from 90.57% to 97.48%;
- evidence F1 remains 21.66%.

The parser/repair item is therefore closed. The remaining failure is semantic:
only 41/99 boolean rows are correct. Four gold-unanswerable rows are incorrectly
classified as `supported` because the relation check accepts lexical token
overlap without proving the question proposition.

### Root cause

The verifier validates that a quote exists and shares relation anchors with the
question. It does not represent the proposition as subject, relation, object,
scope, time, and polarity. High lexical overlap can therefore validate a quote
about a related but different claim. The verifier is correctly advisory, so it
cannot safely repair a wrong primary yes/no answer.

### Required remediation

- Replace lexical relation overlap with a gold-independent proposition
  contract containing subject, relation, object/scope, time, and polarity.
- Require the evidence quote to entail the complete candidate proposition.
  Contradiction and absence of evidence are distinct outcomes.
- Keep the verifier advisory for non-empty primary candidates; improve boolean
  polarity at the primary prompt/evidence boundary instead of flipping answers
  after evaluation.
- Report yes, no, and unanswerable confusion plus proposition failure reasons.
- Freeze a calibration subset before changing thresholds or prompt contracts.

### Closure evidence

Structure validity reaches 100%, no correct primary candidate is damaged,
unsupported lexical-neighbor quotes cannot confirm a candidate, and semantic
F1 reaches 80% on the frozen 159-row subset.

## PERF-001: Latency Evidence Must Remain Quality-Preserving

The latest focused jobs have zero timeouts. Do not interpret text-only
fallback, abstention, incomplete plans, or verifier rejection as a latency
gain. Close this item only after the corrected focused subsets pass quality
gates, publish median and P95, and stay within the fixed simple and
multi-page/numeric latency budgets.

## EVAL-001: The Global Release Gate Is Not Measurable Yet

The frozen G-minus-B QA semantic improvement is still below the required
release gain and lacks a positive paired confidence-interval lower bound.

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

## Current Remediation Wave

The current wave intentionally repairs shared contracts before another model
run:

1. Protection tests for unified identity, metric invariants, and table-cell
   binding are committed separately in `7687d71`, `54aed55`, and `bf91766`.
2. Additive source/page/element/cell fields now survive `EvidenceBundle`; all
   compact candidate and reranker identity inputs remain replayable.
3. Candidate-pool recall, reranker lineage, and equivalent fact support are
   separate additive metrics. Historical strict locator metrics are unchanged.
4. Deterministic numeric scoring inherits only an unambiguous question
   dimension; explicit conflicts remain fatal. Free-text judging uses atomic
   subject/relation/value/unit/time/scope/polarity instructions.
5. Financial tables are parsed into typed Decimal cells. Plans carry row,
   column, and cell IDs; the verifier reloads that exact cell, and period-aware
   formulas no longer default to the first table column.
6. The public CLI gate exposed and closed a pre-existing facade drift:
   `slide_cli.DocQARequest` now forwards the runtime-only route timeout and
   deadline fields without adding or changing any CLI option.
7. Focused unit, benchmark, DocQA, hygiene, and changed-files pre-commit gates
   must pass before submitting the frozen QASPER 159 and FinanceBench 20x4
   validations. A full benchmark remains blocked until the gates above are met.

## Tracked Code Debt

These maintenance risks are not benchmark release claims:

- `ChatPage` still coordinates several workflows.
- Knowledge graph modules should not grow further.
- Preview and Office-conversion broad exception paths require actionable
  diagnostics.
- File-index Gradio event-chain order remains behavior and needs
  characterization coverage.
- Shared metric and identity helpers must remain outside the benchmark runner.
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
