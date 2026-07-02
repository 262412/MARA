# Current Proposal Audit

Last updated: 2026-07-02.

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
| PDF/Word/PPT/Excel/CSV/Markdown/text upload/index/query | Basically complete; diagnostic E2E exists | `FileIndex` type coverage; `benchmark/format_smoke_harness.py`; Task 8 complex-format diagnostic | DOCX/CSV/preview/OCR residual limits                                 |
| Stable `DocQARequest` / `DocQAResponse`                 | Basically complete                       | Typed runtime models and CLI/Web parity coverage                                           | Avoid public JSON/session/request drift                              |
| Controller decisions and evidence contracts             | Basically complete                       | `RouteDecision`, `RetrieveDecision`, `EvidenceBundle`, `VerifyDecision`, `ControllerTrace` | Keep contracts shared across Web/CLI/benchmark                       |
| Route/executor registry                                 | Basically complete                       | Direct, text, page-image, element, graph, hybrid, abstain families                         | Keep backend readiness visible in UI/benchmark                       |
| Text RAG                                                | Basically complete                       | Existing DocQA retrieval/generation and `text_rag` route                                   | Treat as baseline, not as a tuning target                            |
| Controller auto routing                                 | Partly complete                          | Heuristic/structured planner path and `controller_auto` route                              | Route confusion and expected-route analysis                          |
| Page-image RAG                                          | Local-adapted thesis evidence available  | SlideVQA larger25 full matrix; MMDocRAG larger15 visual stability rows                     | No paper-grade or broad large-sample VLM claim                       |
| Element RAG                                             | Partly complete                          | Element parser/ranker/index persistence and sidecar contract                               | Real non-gold OCR/layout quality evidence                            |
| Lightweight GraphRAG                                    | Partly complete                          | Local graph evidence selector and graph-summary path                                       | Claim only local lightweight graph route                             |
| Hybrid RAG                                              | Partly complete                          | Weighted fusion/RRF/learned-ranker hook                                                    | Question-type split before benefit claims                            |
| CRAG-style evaluator                                    | Partly complete                          | Retrieval adequacy, retry, route switch, abstain paths                                     | Threshold calibration and false-abstention analysis                  |
| Claim verification                                      | Partly complete                          | Light/strict verifier and unsupported-claim handling                                       | Do not claim calibrated paper-grade hallucination detection          |
| Citations and evidence metadata                         | Basically complete; local diagnostics    | `agent_trace`, `evidence_metadata`, `evidence_bundle`, `workflow_plan`; Task 6 report      | Paper-grade attribution not configured                               |
| Benchmark harness and route ablations                   | Local-adapted synthesis complete         | Manifest v2, route matrix, route metrics, authority metadata; Task 9 synthesis             | External paper-grade evaluator remains optional/out-of-scope         |
| ALCE/MMDocRAG/RAGTruth-style metrics                    | Local adapted only                       | Local converters/evaluators/report fields; ALCE proxy plumbing                             | No paper-grade external evaluator configured                         |
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

## Current Benchmark Synthesis Status

The current clean run root is
`/mnt/scratch/users/tbczhang/outputs/MARA/benchmark_next_20260701_task0_9_rerun`.
The outputs checklist under that directory remains an execution plan only; this
directory is the canonical status source.

Task 0-9 is closed for the clean rerun as
`local_adapted_thesis_synthesis_complete`. The final synthesis lives under
`09_synthesis/`, especially `task9_final_synthesis.md`,
`thesis_dataset_route_freeze_decision.md`, `final_result_table.csv`,
`route_failure_latency_backend_table.csv`,
`final_evaluator_authority_table.csv`, and `demo_preflight_checklist.md`.

Current thesis evidence decision:

- Primary local-adapted thesis dataset: `slidevqa_test_shard0_multimodal`,
  job `9469112`, 25 examples, full multimodal route matrix, zero prediction
  errors.
- Secondary visual stability evidence:
  `mmdocrag_dev15_available_docs_multimodal`, jobs `9469113` and `9469114`,
  using GPU-ColVision / 8k VLM settings, route-split page-image and hybrid
  evidence, and zero prediction errors.
- Text/core datasets are 10-smoke supporting diagnostics in this clean rerun,
  not main thesis headline datasets.
- Evaluator authority is `local_adapted_only_scope`. No `external_paper_grade`
  result is configured; ALCE proxy evidence is plumbing only.
- ViDoRe remains retrieval-only diagnostic evidence.
- Element RAG, citation attribution, guardrail calibration, and format E2E are
  local diagnostics with explicit residual limits.

Current conclusion:

MARA is ready to be described as a local-first, route-aware, multimodal DocQA
research prototype with a local-adapted thesis evidence package. It is not
ready for official leaderboard, paper-grade external evaluation, production
Self-RAG/CRAG/GraphRAG/MMDocRAG/ColPali reproduction, stable Element RAG
quality, or global superiority claims over `text_rag`.

## No-Benchmark Engineering Closure Items

These items have been closed through code contracts, artifact/report schema,
runbooks, or audit claim boundaries. They should not remain listed as current
unfinished problems.

| Closure item                              | Final conclusion                                                                                                                | Remaining use                                   |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Final thesis claim boundary               | Completed artifacts, local diagnostics, and future work boundaries are frozen                                                   | Apply in dissertation text and tables           |
| Route matrix / evaluator authority draft  | Route reporting roles, authority hierarchy, primary-metric draft, promotion rule, and clean-run local-adapted freeze are recorded | Reopen only for external paper-grade scoring or text/core promotion |
| Paper-grade evaluator interface readiness | Prediction, summary, and report preserve readiness/blocker metadata                                                             | Real external evaluator run remains separate    |
| Citation schema/path consistency          | Metadata citation, inline citation, scored citation, and trace locators are aligned                                             | Quality/attribution analysis remains            |
| CRAG / verifier observability             | True/false abstention, unsupported claim, retry, and route switch are reportable                                                | Threshold calibration remains                   |
| VLM / multimodal runbook productization   | 8000/8001/8002/8003 checks, Slurm template, backend logging, taxonomy, and clean-run visual stability artifacts exist            | Broader VLM generalization remains              |
| Element index engineering contract        | OCR/layout sidecar schema, persisted index contract, coverage report, fixture tests exist                                       | Quality evidence remains                        |
| Format robustness test framework          | PDF/Word/PPTX/Excel/CSV/Markdown/text indexing/query smoke harness exists                                                       | Complex live E2E evidence remains               |
| Failure/routing taxonomy                  | Answer mismatch, timeout, backend unavailable, empty retrieval, false abstention, bad citation, and route family are reportable | Large-sample analysis remains                   |
| Desirable/future-work cleanup             | Trainable router, full GraphRAG, rich graph UI, and media export are scoped extensions or future work                           | Do not claim as completed artifacts             |

## Current Conclusion

MARA is ready to be described as a local-first, route-aware, multimodal DocQA
research prototype with strong engineering artifacts, local diagnostic
evaluation infrastructure, and a clean-run local-adapted thesis evidence
package. It is not ready for official leaderboard claims, paper-grade external
evaluation, production-level system reproduction claims, stable Element RAG
quality claims, or global claims that controller/hybrid/guarded routes are
superior to `text_rag`.
