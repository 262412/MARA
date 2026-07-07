# Evaluation Protocol Freeze Draft

Last updated: 2026-07-07.

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
- Final local-adapted thesis evidence package:
  SlideVQA primary, MMDocRAG secondary visual stability, RAGTruth
  prompt-budget repair evidence, and local dataset-native / adapted metric
  authority.

Not frozen:

- Paper-grade external evaluator scores.
- Text/core dataset promotion beyond smoke-scale supporting diagnostics.
- Any global superiority claim over `text_rag`.
- Element RAG answer-quality improvement.
- Calibrated guardrail or paper-grade attribution claims.
- Full production-style format robustness.
- Original DocQA all-route RAGTruth route-quality repair until the 8002
  retrieval backend is stable and the route-matrix rerun completes.

Current execution status:

- The current final benchmark synthesis root is
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260705_fullsystem_postfix`.
- Earlier required-row synthesis remains available at
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_20260702`.
- RAGTruth prompt-budget repair artifacts live at
  `/mnt/scratch/users/tbczhang/outputs/MARA/ragtruth_prompt_budget_repair_20260707`.
- The 2026-07-05 fullsystem postfix synthesis closed the MMDocRAG route-timeout
  issue for required routes and isolated the remaining execution-error cluster
  to RAGTruth prompt-budget overflow.
- The 2026-07-07 RAGTruth repair validates the prompt-policy fix on the five
  affected examples with direct and lexical local-Qwen reruns, each producing
  5/5 `NO_ERROR`. These repair artifacts are prompt-budget robustness evidence,
  not headline route-quality evidence.
- The original DocQA all-route RAGTruth repair manifest remains blocked by 8002
  retrieval rate limits and should be treated as residual backend evidence.
- Primary local-adapted thesis dataset: `slidevqa_test_shard0_multimodal`,
  job `9559018`, 25 examples, four-route multimodal matrix, zero prediction
  errors.
- Controller route-decision synthesis:
  `final_controller_route_decision_summary.md` is required when interpreting
  the `controller_auto` score.
- Secondary visual stability evidence:
  `mmdocrag_dev15_available_docs_multimodal`, jobs `9559019` and `9559020`,
  with route-split page-image and hybrid evidence under GPU-ColVision / 8k VLM
  settings, plus text baseline diagnostic job `9559021`.
- FinanceBench, QASPER, ALCE, and RAGTruth remain supporting diagnostics unless
  promoted by larger matched reruns.
- Task 2 evaluator authority is closed as `local_adapted_only_scope`;
  `alce=builtin:alce_proxy` is diagnostic plumbing only.
- ViDoRe remains retrieval-only diagnostic evidence.
- Element RAG, guardrail calibration, citation attribution, and format E2E are
  diagnostic-only evidence unless reopened with stronger artifacts.
