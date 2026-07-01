# Residual Risks And Remaining Work

Last updated: 2026-07-01.

This document lists only work that still needs true benchmark evidence,
dissertation result synthesis, or final demo rehearsal. Items already closed
through code contracts, schema alignment, runbooks, or claim boundaries are not
kept here as unfinished problems.

## Essential Remaining Work

1. Final thesis dataset / route / evaluator freeze.

   - Protocol draft is frozen in [Evaluation Protocol](evaluation-protocol.md).
   - Final 2-3 thesis datasets, dissertation route matrix, and evaluator
     authority remain pending.
   - The 2026-06-29/30 10-smoke batch is not sufficient to freeze this:
     FinanceBench, ALCE, QASPER, and RAGTruth required route complement jobs
     `9406278-9406281`, now complete with full artifacts; MMDocRAG required
     route-split repair jobs `9406282-9406286`, now complete with sanity
     artifacts; L40S fallback rows `9408508-9408510`, now complete but not
     closure-ready for page/hybrid; and H100/3-GPU replacement rows
     `9413488-9413490` plus L40S repaired fallback rows `9414048-9414050`,
     now complete but not closure-ready; L40S 8k-context rows
     `9416399-9416401`, now complete with context fixed but route-timeout
     failures remaining; and H100 8k rows `9416402-9416404`, which remain
     pending. L40S timeout-budget diagnostics `9426207-9426208` are submitted
     to determine whether route_timeout=600 was too strict.
   - Close by completing larger matched reruns and identifying which scores are
     external/paper-grade, local dataset-native, or MARA proxy.
   - First larger matched closure jobs are now complete on L40S resources:
     RAGTruth-50 `9426781`, ALCE-50 `9426782`, and SlideVQA-25 `9426783`.
     They close the missing execution gap but do not close the freeze until
     final failure synthesis and the dataset/route/evaluator decision are
     recorded.

2. Paper-grade external evaluation.

   - Interface readiness is complete.
   - The current cycle explicitly closes this as `local_adapted_only_scope`.
     The ALCE proxy run is evaluator plumbing evidence only:
     `paper_grade_ready=False`, blocker `not_paper_grade`.
   - Reopen only if a real paper-grade evaluator with fixed version/config and
     primary metric is configured.

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
   - SlideVQA 10-smoke showed an element coverage gap. MMDocRAG
     `element_rag` repair job `9406283` shows nonzero but sparse coverage
     (2 element records in 1/10 predictions, `avg_element_hit=0`,
     `false_abstention_rate=0.9`). This supports a sparse-coverage failure
     explanation, not a positive Element RAG quality claim.
   - Close by running real non-gold OCR/layout corpus and reporting element
     coverage, element hit, page hit, and answer quality.

5. Page-image / VLM thesis-level stability.

   - Runbook and backend metadata logging exist.
   - Current positive signals remain limited by sample size, duplicate answers,
     answer mismatch, timeout/performance, and backend stability.
   - MMDocRAG 10-smoke job `9389243` timed out and hit VLM 2048 context errors;
     route-split repair uses the 4k VLM wrapper and prompt caps. Text,
     element, visual, hybrid, and controller sanity artifacts are complete and
     no longer show the 2048-context failure.
   - L40S fallback rows `9408508-9408510` are complete with full artifacts, but
     `page_image_rag_vlm` and `hybrid_rag` each still have 3 route timeouts and
     3 VLM 4096-context overflows. This is interim evidence, not closure.
   - L40S repaired fallback jobs `9414048-9414050` completed on `gpu48` with
     `MARA_VLM_EVIDENCE_TEXT_CHARS=120`, but page/hybrid still had 3 route
     timeouts and 3 VLM 4096-context overflows each. The prompt cap alone is
     not enough.
   - Pending H100 4k/120 jobs `9413488-9413490` were cancelled before start to
     avoid repeating the known failure. L40S 8k-context jobs `9416399-9416401`
     are complete and fixed context overflow, but page/hybrid still had route
     timeouts at the 600s route budget. H100 8k jobs `9416402-9416404` are now
     complete as GPU ColVision/performance comparison, and L40S
     timeout-budget diagnostics `9426207-9426208` are complete with
     route_timeout=1200. The remaining MMDocRAG issue is quality/latency, not
     missing execution or context failure.
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
