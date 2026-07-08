# Residual Risks And Remaining Work

Last updated: 2026-07-07.

This document lists only work that still needs true benchmark evidence beyond
the final required benchmark rows, dissertation writing, or final demo
rehearsal. Items already closed through code contracts, schema alignment,
runbooks, final synthesis, or claim boundaries are not kept here as unfinished
problems.

## Final Benchmark Evidence Now Closed

The final local-adapted benchmark evidence has been synthesized under these
roots:

- Fullsystem postfix benchmark:
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260705_fullsystem_postfix`.
- Earlier required-row synthesis:
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_20260702`.
- RAGTruth prompt-budget repair:
  `/mnt/scratch/users/tbczhang/outputs/MARA/ragtruth_prompt_budget_repair_20260707`.

Closed evidence:

- SlideVQA primary local-adapted route comparison, job `9559018`, 25 examples
  and 100 predictions across four routes.
- MMDocRAG secondary visual stability rows, jobs `9559019` and `9559020`, with
  per-job GPU-ColVision / 8k VLM health.
- MMDocRAG text baseline diagnostic, job `9559021`.
- Final tables:
  `09_synthesis/final_main_result_table.csv`,
  `09_synthesis/final_secondary_visual_stability_table.csv`, and
  `09_synthesis/final_failure_latency_backend_table.csv`.
- MMDocRAG required-route timeout repair in the 2026-07-05 fullsystem postfix
  synthesis, with `route_timeout_count=0`.
- RAGTruth long-prompt failure root cause and prompt-policy repair validation:
  the original 11 execution errors were caused by Qwen 4k prompt-budget
  overflow, and the five affected examples completed direct and lexical
  local-Qwen repair reruns with 5/5 `NO_ERROR` in each route family.

## Essential Remaining Work

1. Paper-grade external evaluation.

   - Interface readiness is complete, but no real paper-grade evaluator is
     configured in either the clean Task 0-9 rerun or the 2026-07-02 final
     required benchmark rows.
   - Task 2 is formally closed as `local_adapted_only_scope`. The ALCE proxy
     run verifies evaluator plumbing only:
     `paper_grade_ready=False`, blocker `not_paper_grade`.
   - Reopen only if a real external evaluator with fixed version/config and a
     valid primary metric is configured.

2. Text/core dataset promotion beyond smoke-scale support.

   - FinanceBench, QASPER, ALCE, and RAGTruth have complete 10-smoke route
     matrices in the 2026-07-01 clean rerun.
   - RAGTruth also has a 2026-07-07 prompt-budget repair artifact for the five
     examples affected by the later fullsystem postfix execution-error cluster.
   - They are supporting diagnostics, not main headline thesis datasets,
     because the clean rerun did not promote them through larger matched
     dissertation-scale reruns.
   - Reopen only if the dissertation needs a text/core headline dataset beyond
     the current SlideVQA primary and MMDocRAG secondary package.

3. Element RAG quality on real non-gold OCR/layout records.

   - Engineering and coverage plumbing are closed.
   - Current evidence is sparse coverage, not quality improvement. Task 4
     reports nonzero MMDocRAG element records, but only 1/10 predictions have
     element records, with 2 total records, `avg_element_hit=0`,
     `avg_page_hit=0`, and `false_abstention_rate=0.9`.
   - Close only with broader real OCR/layout coverage plus element hit, page
     hit, and answer-quality improvement over the relevant baselines.

4. Guardrail and attribution calibration.

   - Citation schema, metadata evidence, and verifier observability are
     complete.
   - Task 6 shows metadata/source-page diagnostics, but inline citation
     evidence is absent in current candidates.
   - Task 7 is closed as `local_guardrail_diagnostic_only`: RAGTruth
     `crag_guarded` has TP=0, FP=1, FN=2 in the 10-smoke positive/negative
     sample, with one false abstention.
   - Reopen only for calibrated paper-grade attribution or unsupported-claim
     evaluation.

5. Format robustness beyond demo diagnostics.

   - Task 8 is closed as `format_e2e_diagnostic_only`.
   - The live complex-format diagnostic generated 7 demo-safe samples, indexed
     6/7, and found expected answers in 5/7 query turns.
   - DOCX loader/layout failed without LibreOffice or a direct Office text
     extraction override. CSV indexed but produced empty retrieval evidence.
   - Preview and OCR were not exercised by the CLI path, so production-style
     format robustness remains out of final claim.

6. Original DocQA RAGTruth all-route repair rerun.

   - The prompt-budget bug is fixed and validated through direct/lexical local
     Qwen repair artifacts.
   - The original DocQA repair manifest did not finish because the 8002
     retrieval backend produced repeated rate-limit failures during
     indexing/retrieval.
   - This is a backend availability/evidence gap, not the original 4096-token
     context error. Reopen only if a route-quality repair rerun is required
     after 8002 retrieval is stable.

## Thesis-Ready Reporting Still Needed

1. Dissertation prose, figures, and demo narrative that apply
   [Claim Boundaries](claim-boundaries.md) to the completed final tables.
2. Optional text/core larger matched reruns if a third headline dataset is
   required.
3. Optional paper-grade external evaluator run if the dissertation must include
   official or citable external scores.

## Tracked Code Debt

- `ChatPage` remains large and coordinates multiple workflows.
- Knowledge graph modules are improved but still should not grow further.
- Preview/Office conversion broad exception handling remains a demo risk unless
  failures include actionable diagnostics.
- File-index Gradio event-chain order remains behavior and must be protected by
  characterization tests.
- Benchmark runner/reporting should not absorb new metrics directly; new
  metrics should live in focused helper modules.
