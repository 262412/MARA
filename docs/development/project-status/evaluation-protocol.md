# Evaluation Protocol Freeze Draft

Last updated: 2026-06-30.

This document freezes the protocol draft, not the final benchmark results. It
should be reopened only for a concrete system change, a new regression target,
or a configured paper-grade evaluator.

## Route Matrix Draft

| Dataset family           | Headline routes                                                              | Diagnostic routes                                                | Do not use as main conclusion                                         |
| ------------------------ | ---------------------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------------- |
| QASPER / ALCE / RAGTruth | `direct_answer`, `text_rag`, `hybrid_rag`, `controller_auto`, `crag_guarded` | `element_rag` only when element records exist                    | `page_image_rag_vlm`, unless samples contain true image/page evidence |
| FinanceBench             | `direct_answer`, `text_rag`, `controller_auto`, `crag_guarded`               | `hybrid_rag`, numeric/error diagnostics                          | Controller/guarded improvement claims                                 |
| SlideVQA / MMDocRAG      | `text_rag`, `page_image_rag_vlm`, `hybrid_rag`, `controller_auto`            | `element_rag` as coverage / element diagnostic                   | Element quality claims until non-gold OCR/layout proves improvement   |
| ViDoRe                   | `colqwen_retriever_only`, `colpali_retriever_only`                           | Full QA generation only when answer-bearing route/data are ready | Full QA benchmark claim without new artifacts                         |
| Format robustness        | Indexing/query smoke by file type                                            | Loader, preview, OCR, layout failure taxonomy                    | Formal QA benchmark claim                                             |

Reporting rules:

- `direct_answer` is a diagnostic baseline for no-retrieval behavior.
- `text_rag` is the default retrieval baseline.
- `controller_auto`, `hybrid_rag`, and `crag_guarded` may be reported by
  dataset, question type, modality, and failure class; do not claim global
  superiority over `text_rag`.
- `page_image_rag_vlm` can support multimodal route evidence for
  SlideVQA/MMDocRAG only with backend health, latency, timeout,
  answer-mismatch, and sample-size reporting.
- `element_rag` is currently an element coverage, persistence, and locator
  diagnostic route; do not use it as an answer-quality headline route until
  real non-gold OCR/layout evidence supports that claim.

## Evaluator Authority Draft

| Authority level         | Purpose                                                                                                   | Headline use                   |
| ----------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------ |
| `external_paper_grade`  | Real external evaluator with `paper_grade=true`, fixed evaluator version/config, and valid primary metric | Allowed when configured        |
| `local_dataset_native`  | Dataset-family local scoring adapter                                                                      | Current default headline       |
| `mara_diagnostic_proxy` | MARA internal diagnostic score for answer/evidence/citation/grounding/controller behavior                 | Never final benchmark headline |
| `generic_diagnostic`    | EM/F1/ANLS, page hit, citation recall, latency, failure class                                             | Secondary diagnostics only     |

Promotion rules:

- If an external evaluator is configured and returns `paper_grade=true` plus a
  valid `primary_metric`, headline score uses `external_paper_grade`.
- Evaluator readiness is represented through `paper_grade_ready` and
  `paper_grade_blockers`.
- Common blockers include `not_configured`, `not_paper_grade`,
  `missing_primary_metric`, `primary_metric_missing_from_metrics`, and
  `failed`.
- Without external evaluator readiness, headline score uses
  `local_dataset_native` and must be labelled as local adapted /
  dataset-native local result.
- `mara_diagnostic_proxy` and `generic_diagnostic` never upgrade into official
  or paper-grade results.
- Historical artifacts missing authority fields are not retroactively promoted.
  Use an explicit rescoring artifact or new run.

## Dataset Primary Metric Draft

| Dataset      | Primary without external evaluator                  | Secondary diagnostics                                                                          |
| ------------ | --------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| FinanceBench | Local answer correctness / native score             | Numeric match, page hit, false abstention, wrong-source/wrong-page failures                    |
| QASPER       | Local answer F1 / native score                      | Evidence hit, citation metadata recall, answer length, multi-point extraction failures         |
| RAGTruth     | Local hallucination / unsupported-claim style score | Abstention, false abstention, rewrite skipped, unsupported-claim diagnostics                   |
| ALCE         | Local correctness + citation-style score            | Metadata citation recall/precision, inline citation recall/precision                           |
| SlideVQA     | Local visual QA F1 / native score                   | Page hit, VLM backend status, latency, answer mismatch, timeout                                |
| MMDocRAG     | Local visual QA / native score                      | Page hit, element coverage, citation recall, VLM context/timeout failures                      |
| ViDoRe       | Retrieval diagnostic score only                     | Retriever hit, page evidence, MRR-like diagnostics when available; full QA separately labelled |

## Freeze Status

Frozen:

- Protocol-level route categories.
- Route reporting roles.
- Evaluator authority hierarchy.
- Score promotion rule.
- Dataset primary-metric draft.

Not frozen:

- Final 2-3 thesis main datasets.
- Final route matrix for dissertation tables.
- Final evaluator authority with paper-grade external scores.
- Any superiority claim over `text_rag`.

Current execution status:

- The active 2026-06-29/30 run root is
  `/mnt/scratch/users/tbczhang/outputs/MARA/benchmark_next_20260629`.
- Route-matrix complement jobs `9406278-9406281` are complete for FinanceBench,
  ALCE, QASPER, and RAGTruth.
- MMDocRAG route-split repair/sanity jobs `9406282-9406286` are tracked after
  the first all-route job timed out. Text and element jobs `9406282-9406283`
  are complete; visual/controller sanity rows `9406284-9406286` are also
  complete with artifact four-tuples.
- MMDocRAG element coverage is nonzero but sparse, so it is evidence for a
  sparse-coverage failure rather than a positive Element RAG quality claim.
- The MMDocRAG visual sanity run no longer shows the 2048-context failure, but
  L40S fallback rows `9408508-9408510` show the 4k prompt cap is still too
  tight for page/hybrid: each has 3 route timeouts and 3 VLM 4096-context
  overflows. L40S repaired fallback jobs `9414048-9414050` completed on
  `gpu48` with evidence_text_chars=120 but still overflowed 4096 context for
  page/hybrid. H100/3-GPU 4k-context jobs `9413488-9413490` were cancelled
  before start. L40S 8k-context rows `9416399-9416401` completed and fixed
  context overflow, but page/hybrid still have route-timeout/performance
  failures. H100 8k rows `9416402-9416404` remain pending, and L40S
  timeout-budget diagnostics `9426207-9426208` are submitted with
  route_timeout=1200.
- Task 2 evaluator authority is closed for this cycle as
  `local_adapted_only_scope`; `alce=builtin:alce_proxy` is diagnostic plumbing
  only.
- Freeze still waits for H100 replacement artifacts, larger matched reruns, and
  failure synthesis.
