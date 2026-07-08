# Current Proposal Audit

Last updated: 2026-07-07.

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

| Proposal item                                           | Current status                            | Evidence                                                                                               | Remaining work                                                       |
| ------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| Local-first Web/CLI DocQA runtime                       | Basically complete                        | Shared `ktem.docqa.DocQARuntime`; `MARA docqa`; Web request builder                                    | Preserve parity tests for new request/session fields                 |
| PDF/Word/PPT/Excel/CSV/Markdown/text upload/index/query | Basically complete; diagnostic E2E exists | `FileIndex` type coverage; `benchmark/format_smoke_harness.py`; Task 8 complex-format diagnostic       | DOCX/CSV/preview/OCR residual limits                                 |
| Stable `DocQARequest` / `DocQAResponse`                 | Basically complete                        | Typed runtime models and CLI/Web parity coverage                                                       | Avoid public JSON/session/request drift                              |
| Controller decisions and evidence contracts             | Basically complete                        | `RouteDecision`, `RetrieveDecision`, `EvidenceBundle`, `VerifyDecision`, `ControllerTrace`             | Keep contracts shared across Web/CLI/benchmark                       |
| Route/executor registry                                 | Basically complete                        | Direct, text, page-image, element, graph, hybrid, abstain families                                     | Keep backend readiness visible in UI/benchmark                       |
| Text RAG                                                | Basically complete                        | Existing DocQA retrieval/generation and `text_rag` route                                               | Treat as baseline, not as a tuning target                            |
| Controller auto routing                                 | Partly complete                           | Heuristic/structured planner path and `controller_auto` route                                          | Route confusion and expected-route analysis                          |
| Page-image RAG                                          | Local-adapted thesis evidence available   | Final SlideVQA 25 full matrix; final MMDocRAG 15 visual stability rows                                 | No paper-grade or broad large-sample VLM claim                       |
| Element RAG                                             | Partly complete                           | Element parser/ranker/index persistence and sidecar contract                                           | Real non-gold OCR/layout quality evidence                            |
| Lightweight GraphRAG                                    | Partly complete                           | Local graph evidence selector and graph-summary path                                                   | Claim only local lightweight graph route                             |
| Hybrid RAG                                              | Partly complete                           | Weighted fusion/RRF/learned-ranker hook                                                                | Question-type split before benefit claims                            |
| CRAG-style evaluator                                    | Partly complete                           | Retrieval adequacy, retry, route switch, abstain paths                                                 | Threshold calibration and false-abstention analysis                  |
| Claim verification                                      | Partly complete                           | Light/strict verifier and unsupported-claim handling                                                   | Do not claim calibrated paper-grade hallucination detection          |
| Citations and evidence metadata                         | Basically complete; local diagnostics     | `agent_trace`, `evidence_metadata`, `evidence_bundle`, `workflow_plan`; Task 6 report                  | Paper-grade attribution not configured                               |
| Benchmark harness and route ablations                   | Local-adapted final synthesis complete    | Manifest v2, route matrix, route metrics, authority metadata; 2026-07-05 fullsystem postfix synthesis  | External paper-grade evaluator remains optional/out-of-scope         |
| ALCE/MMDocRAG/RAGTruth-style metrics                    | Local adapted only                        | Local converters/evaluators/report fields; ALCE proxy plumbing; RAGTruth prompt-budget repair evidence | No paper-grade external evaluator configured                         |
| Web UI workbench                                        | Partly complete                           | Source browser, preview, chat, route controls, trace, graph, Studio artifacts                          | Final UI information architecture polish                             |
| Automated tests                                         | Partly complete                           | Focused benchmark/ktem/slide_cli tests                                                                 | Continue targeted gates; avoid root `pytest -q` as default readiness |

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

The current final benchmark evidence roots are:

- Fullsystem postfix benchmark:
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260705_fullsystem_postfix`.
- Earlier required-row synthesis:
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_20260702`.
- RAGTruth prompt-budget repair:
  `/mnt/scratch/users/tbczhang/outputs/MARA/ragtruth_prompt_budget_repair_20260707`.

The outputs directory remains an execution artifact only; this directory is
the canonical status source.

The 2026-07-05 fullsystem postfix benchmark is the latest synthesis used for
claim-boundary decisions. It incorporated the MMDocRAG controller timeout
repair with `route_timeout_count=0` for required routes. Its only remaining
execution-error cluster was RAGTruth: 3 `controller_auto`, 3 `crag_guarded`,
and 5 `text_rag` errors. The root cause was not Slurm scheduling or a timeout
storm; it was Qwen 4k prompt-budget overflow from long RAGTruth
`gold_answer_v1` prompts that bypassed benchmark question/source truncation.

The 2026-07-07 RAGTruth repair validates the prompt-policy fix on the five
affected examples:

- Direct prompt-budget local-Qwen rerun: 5 predictions, 5 `NO_ERROR`.
- Lexical text local-Qwen rerun with retrieved evidence: 5 predictions,
  5 `NO_ERROR`, three retrieved hits per example.
- All repair prompts carried the truncation marker and avoided maximum-context
  / `4097` / input-token errors under the same local Qwen 4k context.
- The original DocQA all-route repair manifest is still not closed as
  route-quality evidence because the 8002 retrieval backend produced repeated
  rate-limit failures during indexing/retrieval.

Current thesis evidence decision:

- Primary local-adapted thesis dataset: `slidevqa_test_shard0_multimodal`,
  job `9559018`, 25 examples, 100 predictions across
  `text_rag`, `page_image_rag_vlm`, `hybrid_rag`, and `controller_auto`, zero
  prediction errors.
- Secondary visual stability evidence:
  `mmdocrag_dev15_available_docs_multimodal`, jobs `9559019` and `9559020`,
  using GPU-ColVision / 8k VLM settings, route-split page-image and hybrid
  evidence, plus text baseline diagnostic job `9559021`, all with zero
  prediction errors.
- Controller trace evidence:
  `final_controller_route_decision_summary.md` records that the final
  `controller_auto` row selected internal `hybrid_rag` with route-switch traces.
- Text/core datasets are supporting diagnostics unless promoted by larger
  matched reruns; RAGTruth now has prompt-budget repair evidence, but not a
  completed original DocQA all-route repair rerun.
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
quality, or global superiority claims over `text_rag`. RAGTruth long-prompt
execution failures can be described as fixed for the prompt-budget policy and
validated on affected examples through direct/lexical local-Qwen reruns, but
not as a completed original DocQA route-matrix quality rerun.

## No-Benchmark Engineering Closure Items

These items have been closed through code contracts, artifact/report schema,
runbooks, or audit claim boundaries. They should not remain listed as current
unfinished problems.

| Closure item                              | Final conclusion                                                                                                                  | Remaining use                                                       |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Final thesis claim boundary               | Completed artifacts, local diagnostics, and future work boundaries are frozen                                                     | Apply in dissertation text and tables                               |
| Route matrix / evaluator authority draft  | Route reporting roles, authority hierarchy, primary-metric draft, promotion rule, and clean-run local-adapted freeze are recorded | Reopen only for external paper-grade scoring or text/core promotion |
| Paper-grade evaluator interface readiness | Prediction, summary, and report preserve readiness/blocker metadata                                                               | Real external evaluator run remains separate                        |
| Citation schema/path consistency          | Metadata citation, inline citation, scored citation, and trace locators are aligned                                               | Quality/attribution analysis remains                                |
| CRAG / verifier observability             | True/false abstention, unsupported claim, retry, and route switch are reportable                                                  | Threshold calibration remains                                       |
| VLM / multimodal runbook productization   | 8000/8001/8002/8003 checks, Slurm template, backend logging, taxonomy, and clean-run visual stability artifacts exist             | Broader VLM generalization remains                                  |
| Element index engineering contract        | OCR/layout sidecar schema, persisted index contract, coverage report, fixture tests exist                                         | Quality evidence remains                                            |
| Format robustness test framework          | PDF/Word/PPTX/Excel/CSV/Markdown/text indexing/query smoke harness exists                                                         | Complex live E2E evidence remains                                   |
| Failure/routing taxonomy                  | Answer mismatch, timeout, backend unavailable, empty retrieval, false abstention, bad citation, and route family are reportable   | Large-sample analysis remains                                       |
| Desirable/future-work cleanup             | Trainable router, full GraphRAG, rich graph UI, and media export are scoped extensions or future work                             | Do not claim as completed artifacts                                 |
| RAGTruth prompt-budget repair             | Long `gold_answer_v1` prompt overflow is fixed at prompt-policy level and validated on affected examples                          | Original DocQA all-route repair waits for stable 8002 retrieval     |

## Current Conclusion

MARA is ready to be described as a local-first, route-aware, multimodal DocQA
research prototype with strong engineering artifacts, local diagnostic
evaluation infrastructure, and a clean-run local-adapted thesis evidence
package. It is not ready for official leaderboard claims, paper-grade external
evaluation, production-level system reproduction claims, stable Element RAG
quality claims, or global claims that controller/hybrid/guarded routes are
superior to `text_rag`. The final dissertation claim should explicitly separate
completed local-adapted artifacts from residual backend-dependent reruns.
