# Reproducing the DocQA-Inspect diagnostic analysis

The paper uses DocQA-Inspect; released software and historical artifacts retain the name MARA. Original filenames, commands, schemas, and captured answer strings are preserved.

No model calls or new predictions are required to reproduce the tables from the released metric records. This is a reanalysis of existing artifacts, not an end-to-end system rerun.

## Inputs and identities

Use mara-full-system-benchmark-synthesis-v0.0.40.zip, supplied unchanged with this guide. Its SHA-256 is:

7fabae169ef270dd2e6ee5edd1aa74841f3ffa100f3bf47bb5fa6139f866cafb

The release source anchor is v0.0.40, commit 37487f35610076c1016e1b59d3bf982388d1a275. The synthesis report is dated 2026-07-05. Neither identifier substitutes for absent per-job build metadata.

## Checks performed for this revision

1. Read statistical_per_example_metric_records.csv: 3,540 rows, 3,540 unique dataset/example/route keys, and 1,090 unique dataset/example keys.
2. Group by dataset and route. Reconcile counts and rounded means with all 20 rows of statistical_main_result_table.csv. Missing metric cells stay missing.
3. For every released baseline/candidate pair, join by dataset and example_id. Compute rounded four-decimal F1 differences, and reconcile wins, losses, ties, and sample count.
4. Use benchmark/statistical_significance.py from the stated source anchor. Call bootstrap_ci_by_dataset_route with metric="f1", iterations=1000, seed=20260705. All 14 means and intervals reproduce the released CSV.
5. Group controller_auto records by dataset and controller_final_route, keeping missing final-route records as errors rather than dropping them. There are ten successful switch flags: four FinanceBench and six MMDocRAG.
6. Pair the two SlideVQA configurations. F1, EM, native score, both citation recall measures, and page hit are identical for every one of 120 pairs. This is a measurement limitation, not evidence that the generators are equivalent.
7. For each dataset/question, define the comparison envelope as maximum F1 among configurations other than controller_auto. Report the signed mean difference separately from mean(max(difference, 0)). The latter is the release's regret field.

The supplementary revision-evidence.json records the checked values and interpretation limits. The source paper's diagnostic_tables.tex presents all quality, operational, and paired rows.

## Definitions needed for interpretation

- Four-decimal rounding is inherited from the released per-example metrics.
- Bootstrap percentiles use the sorted value at Python round((n - 1) * fraction), with fractions 0.025 and 0.975 across 1,000 resampled means.
- Reported p95 time uses the same nearest rounded-index convention on recorded total_seconds.
- Missing cells are not zero. Configured generator identity does not certify actual invocation.
- The oracle compares whole configurations, can include an unselectable direct or guarded configuration, and can use another generator. It is not a strict reachable-route oracle.
- Citation locator recall and self-reported unsupported-claim rate do not establish semantic entailment or factual correctness.
- Non-significant paired differences do not prove equivalence.
- Parse/retrieval timing fields are zero in this bundle and cannot establish that these operations cost no time.
- Different MMDocRAG manifests and timeout budgets limit causal latency/reliability comparisons.
- The ZIP lacks answer strings and effective per-job route manifests. Do not infer the cause of SlideVQA score equality from the metric CSV alone.

## New case, separate from the historical synthesis

`case_study/README.md` explains the executed source-selection task, offline checks,
and optional new API execution. The complete first before/after pair and negative
independent repetition are retained. `answer-stages.json` keeps provider output,
pre-verification, pre-guardrail, displayed and scoring answers distinct. Its
scoring projection is explicitly identity, not the historical benchmark adapter.
No historical aggregate, row, or input archive is replaced by these case records.
