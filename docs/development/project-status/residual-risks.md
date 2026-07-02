# Residual Risks And Remaining Work

Last updated: 2026-07-02.

This document lists only work that still needs true benchmark evidence,
dissertation result synthesis, or final demo rehearsal. Items already closed
through code contracts, schema alignment, runbooks, or claim boundaries are not
kept here as unfinished problems.

## Essential Remaining Work

1. Paper-grade external evaluation.

   - Interface readiness is complete, but no real paper-grade evaluator is
     configured in the clean Task 0-9 rerun.
   - Task 2 is formally closed as `local_adapted_only_scope`. The ALCE proxy
     run verifies evaluator plumbing only:
     `paper_grade_ready=False`, blocker `not_paper_grade`.
   - Reopen only if a real external evaluator with fixed version/config and a
     valid primary metric is configured.

2. Text/core dataset promotion beyond smoke-scale support.

   - FinanceBench, QASPER, ALCE, and RAGTruth have complete 10-smoke route
     matrices in the 2026-07-01 clean rerun.
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

## Thesis-Ready Reporting Still Needed

1. Dissertation prose, tables, figures, and demo narrative that apply
   [Claim Boundaries](claim-boundaries.md).
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
