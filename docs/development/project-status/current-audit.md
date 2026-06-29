# Current Proposal Audit

Last updated: 2026-06-29.

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
