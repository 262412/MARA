# Residual Risks And Remaining Work

Last updated: 2026-06-29.

This document lists only work that still needs true benchmark evidence,
dissertation result synthesis, or final demo rehearsal. Items already closed
through code contracts, schema alignment, runbooks, or claim boundaries are not
kept here as unfinished problems.

## Essential Remaining Work

1. Final thesis dataset / route / evaluator freeze.

   - Protocol draft is frozen in [Evaluation Protocol](evaluation-protocol.md).
   - Final 2-3 thesis datasets, dissertation route matrix, and evaluator
     authority remain pending.
   - Close by completing larger matched reruns and identifying which scores are
     external/paper-grade, local dataset-native, or MARA proxy.

2. Paper-grade external evaluation.

   - Interface readiness is complete.
   - Representative artifacts still mostly show external evaluators as
     `not_configured`.
   - Close by configuring and running at least one paper-grade or clearly
     citable external evaluator, or explicitly limiting the dissertation to
     local adapted metrics.

3. Controller / hybrid / guarded effectiveness.

   - Engineering loop exists.
   - Current FinanceBench/QASPER evidence does not show stable global
     improvement over text baseline.
   - Close by reporting benefits and failures by dataset, question type,
     modality, and failure class.

4. Element RAG quality on real non-gold OCR/layout records.

   - Engineering contract is closed.
   - Quality conclusion remains open: manifest-level runs can still have
     `element_records=0`, and persisted records have not yet produced stable
     answer-quality gains.
   - Close by running real non-gold OCR/layout corpus and reporting element
     coverage, element hit, page hit, and answer quality.

5. Page-image / VLM thesis-level stability.

   - Runbook and backend metadata logging exist.
   - Current positive signals remain limited by sample size, duplicate answers,
     answer mismatch, timeout/performance, and backend stability.
   - Close by fixing backend choice, running larger samples, and reporting
     health, latency, taxonomy distribution, and reproducible commands.

6. Citation and attribution quality.

   - Citation schema/path consistency is closed.
   - Historical artifacts need rerun/rescore for latest trace fields.
   - Claim attribution is not paper-grade.
   - Close by reporting metadata citation vs inline citation differences and
     unsupported-claim analysis on thesis datasets.

7. CRAG-style evaluator and claim verifier calibration.

   - Observability is closed.
   - Lightweight/rule-level verifier is not calibrated paper-grade detection.
   - QASPER/guarded still risks over-interception and false abstention.
   - Close by analysing true/false abstention and unsupported-claim
     false-positive/false-negative behavior with the new observability fields.

8. Format robustness E2E evidence.

   - Fixture-level smoke harness exists.
   - Real complex PPTX, Excel, formulas, and charts still need
     dissertation-level end-to-end evidence.
   - Close with live/Slurm DocQA runs over realistic complex samples and
     preview/OCR/layout/loader failure taxonomy.

## Thesis-Ready Reporting Still Needed

1. Large-sample failure analysis by route, modality, question type, and backend
   status.
2. Routing accuracy or expected-route evaluation based on the finished routing
   taxonomy.
3. Final latency, cost, and backend-type tables.
4. Final demo preflight covering text LLM, embedding/reranker, VLM, ColVision,
   `KH_APP_DATA_DIR`, DB/vectorstore, and selected dataset paths.
5. Dissertation prose, tables, figures, and demo narrative that apply
   [Claim Boundaries](claim-boundaries.md).

## Tracked Code Debt

- `ChatPage` remains large and coordinates multiple workflows.
- Knowledge graph modules are improved but still should not grow further.
- Preview/Office conversion broad exception handling remains a demo risk unless
  failures include actionable diagnostics.
- File-index Gradio event-chain order remains behavior and must be protected by
  characterization tests.
- Benchmark runner/reporting should not absorb new metrics directly; new
  metrics should live in focused helper modules.
