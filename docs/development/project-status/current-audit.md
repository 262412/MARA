# Current Proposal Audit

Last updated: 2026-07-01.

This is the canonical current status source for MARA proposal alignment. The
old `docs/development/proposal_project_audit_2026-06-25.md` path is now a
compatibility pointer to this directory.

## Source Inputs

- Proposal: `docs/proposal_comp702.pdf`, created 2026-06-10.
- Repository: `/mnt/scratch/users/tbczhang/projects/MARA`.
- Development constraints:
  - [Codebase Hygiene Contract](../codebase-hygiene-contract.md)
  - [Storage Layout Contract](../storage-layout-contract.md)
- Thesis scope reference: [MARA Thesis MVP](../../mara_thesis_mvp.md).
- Phase conclusions: [Phase Closures](phase-closures.md).
- Claim limits: [Claim Boundaries](claim-boundaries.md).
- Evaluation protocol: [Evaluation Protocol](evaluation-protocol.md).
- Remaining work: [Residual Risks](residual-risks.md).

## Document Governance

This directory replaces scattered phase-summary documents as the current status
source.

- Use this file for the proposal-to-current-state overview.
- Use [Phase Closures](phase-closures.md) for final phase summaries.
- Use [Claim Boundaries](claim-boundaries.md) when writing dissertation,
  proposal-facing reports, or demo narrative.
- Use [Evaluation Protocol](evaluation-protocol.md) when deciding route matrix,
  evaluator authority, and score promotion.
- Use [Residual Risks](residual-risks.md) for work that still needs true
  benchmark evidence or paper/demo application.
- Treat [Archive](archive/README.md) and `docs/superpowers/plans/` as historical
  provenance only.

## Environment Status

The required MARA storage layout remains:

- Repository root: `/mnt/scratch/users/tbczhang/projects/MARA`.
- `.venv`: symlink to `/mnt/fastscratch/users/tbczhang/envs/mara`.
- `.venv/bin/python`: fastscratch uv Python.
- Cache/runtime variables such as `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`,
  `HF_HOME`, `TIKTOKEN_CACHE_DIR`, `CODEX_HOME`, and `KH_APP_DATA_DIR` stay on
  scratch/fastscratch.
- Repository root must not contain `data/`, `datasets/`, or `outputs/`.

Always re-run the storage preflight before `uv`, tests, model calls, DocQA
indexing, dataset syncs, Slurm jobs, or large downloads.

## Proposal Matrix

| Proposal item                                           | Current status                           | Evidence                                                                                   | Remaining work                                                       |
| ------------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| Local-first Web/CLI DocQA runtime                       | Basically complete                       | Shared `ktem.docqa.DocQARuntime`; `MARA docqa`; Web request builder                        | Preserve parity tests for new request/session fields                 |
| PDF/Word/PPT/Excel/CSV/Markdown/text upload/index/query | Basically complete; fixture smoke exists | `FileIndex` type coverage; `benchmark/format_smoke_harness.py`                             | Real complex PPTX/Excel/formula/chart E2E evidence                   |
| Stable `DocQARequest` / `DocQAResponse`                 | Basically complete                       | Typed runtime models and CLI/Web parity coverage                                           | Avoid public JSON/session/request drift                              |
| Controller decisions and evidence contracts             | Basically complete                       | `RouteDecision`, `RetrieveDecision`, `EvidenceBundle`, `VerifyDecision`, `ControllerTrace` | Keep contracts shared across Web/CLI/benchmark                       |
| Route/executor registry                                 | Basically complete                       | Direct, text, page-image, element, graph, hybrid, abstain families                         | Keep backend readiness visible in UI/benchmark                       |
| Text RAG                                                | Basically complete                       | Existing DocQA retrieval/generation and `text_rag` route                                   | Treat as baseline, not as a tuning target                            |
| Controller auto routing                                 | Partly complete                          | Heuristic/structured planner path and `controller_auto` route                              | Route confusion and expected-route analysis                          |
| Page-image RAG                                          | Partly complete                          | Local smoke retriever, ColVision HTTP retriever, Qwen-VL adapter                           | Larger stable VLM rerun and latency/error analysis                   |
| Element RAG                                             | Partly complete                          | Element parser/ranker/index persistence and sidecar contract                               | Real non-gold OCR/layout quality evidence                            |
| Lightweight GraphRAG                                    | Partly complete                          | Local graph evidence selector and graph-summary path                                       | Claim only local lightweight graph route                             |
| Hybrid RAG                                              | Partly complete                          | Weighted fusion/RRF/learned-ranker hook                                                    | Question-type split before benefit claims                            |
| CRAG-style evaluator                                    | Partly complete                          | Retrieval adequacy, retry, route switch, abstain paths                                     | Threshold calibration and false-abstention analysis                  |
| Claim verification                                      | Partly complete                          | Light/strict verifier and unsupported-claim handling                                       | Do not claim calibrated paper-grade hallucination detection          |
| Citations and evidence metadata                         | Basically complete                       | `agent_trace`, `evidence_metadata`, `evidence_bundle`, `workflow_plan`                     | Attribution-quality analysis still needed                            |
| Benchmark harness and route ablations                   | Framework complete; evaluation not final | Manifest v2, route matrix, route metrics, authority metadata                               | External paper-grade evaluator and final thesis protocol             |
| ALCE/MMDocRAG/RAGTruth-style metrics                    | Partly complete                          | Local converters/evaluators/report fields                                                  | External evaluators mostly `not_configured`                          |
| Web UI workbench                                        | Partly complete                          | Source browser, preview, chat, route controls, trace, graph, Studio artifacts              | Final UI information architecture polish                             |
| Automated tests                                         | Partly complete                          | Focused benchmark/ktem/slide_cli tests                                                     | Continue targeted gates; avoid root `pytest -q` as default readiness |

## Completed Or Basically Complete

1. Public product surface is established: `MARA`, `MARA-cli`, `MARA docqa`,
   `MARA app`, `MARA model`, and `MARA platform`.
2. Shared DocQA runtime is implemented across Web and CLI.
3. Controller contracts and route registry are present in code.
4. Self-RAG-inspired control semantics exist at program level: route selection,
   retrieval decision, evidence evaluation, retry, route switch, verify,
   revise, and abstain.
5. Benchmark framework is usable and distinguishes external/paper-grade,
   local dataset-native, and MARA diagnostic proxy scoring.
6. Study artifact generation exceeds the minimum proposal MVP, while real
   audio/video media export remains a scoped extension.

## Active Benchmark Repair Status

The active run root is
`/mnt/scratch/users/tbczhang/outputs/MARA/benchmark_next_20260629`.

The first 10-smoke batch is useful as health and diagnostic evidence, but it is
not final thesis evidence. The current repair state is:

- FinanceBench, ALCE, QASPER, and RAGTruth route-matrix complement jobs
  `9406278-9406281` are complete with full artifact four-tuples.
- MMDocRAG first run `9389243` timed out; route-split repair/sanity jobs
  `9406282-9406286` are tracked. `text_rag`/`element_rag` jobs
  `9406282-9406283` are complete; visual/controller sanity rows
  `9406284-9406286` are also complete with artifact four-tuples.
- MMDocRAG `element_rag` now has nonzero but sparse element coverage evidence
  (2 records in 1/10 predictions), so it supports a sparse-coverage failure
  explanation rather than a positive Element RAG claim.
- MMDocRAG visual sanity no longer shows the earlier 2048-context or
  DictionaryObject failures. L40S fallback limit=10 rows `9408508-9408510`
  completed with artifact four-tuples, but `page_image_rag_vlm` and
  `hybrid_rag` still have route timeouts plus VLM 4096-context overflows.
  H100/3-GPU replacement jobs `9413488-9413490` are submitted to test GPU
  ColVision, a 600s route timeout, and evidence_text_chars=120. L40S repaired
  fallback jobs `9414048-9414050` completed on `gpu48` with the same prompt cap
  but still had page/hybrid route timeouts plus 4096-context overflows. The
  L40S 8k-context rows `9416399-9416401` are complete and fixed VLM context
  overflow, but page/hybrid still have route-timeout/performance failures. H100
  8k rows `9416402-9416404` remain pending as GPU ColVision/performance
  comparison. L40S timeout-budget diagnostics `9426207-9426208` are submitted
  with route_timeout=1200.
- External evaluator Task 2 is closed for this cycle as
  `local_adapted_only_scope`; the ALCE proxy is not paper-grade.
- Derived reports now exist under the run root for route matrix,
  controller/hybrid/guarded behavior, element coverage, evaluator authority,
  citation attribution, guardrail calibration, and synthesis.
- Larger matched closure jobs have been submitted on L40S resources:
  RAGTruth-50 `9426781`, ALCE-50 `9426782`, and SlideVQA-25 `9426783`. They
  are not freeze evidence until the artifact four-tuples and failure synthesis
  are complete. These rows are now complete with full artifact four-tuples.
  RAGTruth-50 supports guardrail calibration/failure analysis, ALCE-50 supports
  `text_rag` as the strongest route and `hybrid_rag` as diagnostic, and
  SlideVQA-25 supports visual routes over text while preserving Element RAG as
  a coverage failure.
- H100 MMDocRAG rows `9416402-9416404` and L40S timeout-budget rows
  `9426207-9426208` are complete. They close the missing execution/context/
  timeout evidence gap, but MMDocRAG remains a quality/latency residual risk.

Do not freeze final datasets, route table, or evaluator authority until
failure synthesis is updated and the final thesis dataset/route/evaluator
decision is explicitly recorded.

## No-Benchmark Engineering Closure Items

These items have been closed through code contracts, artifact/report schema,
runbooks, or audit claim boundaries. They should not remain listed as current
unfinished problems.

| Closure item                              | Final conclusion                                                                                                                | Remaining use                                   |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Final thesis claim boundary               | Completed artifacts, local diagnostics, and future work boundaries are frozen                                                   | Apply in dissertation text and tables           |
| Route matrix / evaluator authority draft  | Route reporting roles, authority hierarchy, primary-metric draft, and promotion rule are recorded                               | Final thesis datasets still need larger results |
| Paper-grade evaluator interface readiness | Prediction, summary, and report preserve readiness/blocker metadata                                                             | Real external evaluator run remains separate    |
| Citation schema/path consistency          | Metadata citation, inline citation, scored citation, and trace locators are aligned                                             | Quality/attribution analysis remains            |
| CRAG / verifier observability             | True/false abstention, unsupported claim, retry, and route switch are reportable                                                | Threshold calibration remains                   |
| VLM / multimodal runbook productization   | 8000/8001/8002/8003 checks, Slurm template, backend logging, taxonomy exist                                                     | Larger VLM rerun remains                        |
| Element index engineering contract        | OCR/layout sidecar schema, persisted index contract, coverage report, fixture tests exist                                       | Quality evidence remains                        |
| Format robustness test framework          | PDF/Word/PPTX/Excel/CSV/Markdown/text indexing/query smoke harness exists                                                       | Complex live E2E evidence remains               |
| Failure/routing taxonomy                  | Answer mismatch, timeout, backend unavailable, empty retrieval, false abstention, bad citation, and route family are reportable | Large-sample analysis remains                   |
| Desirable/future-work cleanup             | Trainable router, full GraphRAG, rich graph UI, and media export are scoped extensions or future work                           | Do not claim as completed artifacts             |

## Current Conclusion

MARA is ready to be described as a local-first, route-aware, multimodal DocQA
research prototype with strong engineering artifacts and local diagnostic
evaluation infrastructure. It is not yet ready for broad claims that
controller/hybrid/guarded, VLM, or element routes are stably superior to text
RAG, nor for claims of paper-grade external evaluation.
