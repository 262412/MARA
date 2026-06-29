# Phase Closures

Last updated: 2026-06-29.

This document keeps only final phase conclusions. It intentionally excludes
development-by-development logs, failed attempts, and repeated rerun details.

## Phase 0 - Verifiable Environment

Status: complete, closed on 2026-06-25.

Goal: restore a verifiable environment before tests, indexing, benchmark runs,
or model calls.

Final conclusion:

- fastscratch file count returned below soft quota.
- Cleanup only removed regenerable caches such as uv package/build/temp cache
  and pip HTTP/selfcheck cache.
- It did not remove `envs/`, `mara_runtime/`, Hugging Face cache, model weights,
  datasets, benchmark artifacts, or GPU compilation caches that could be used
  by active services.
- `.venv` remained a symlink to `/mnt/fastscratch/users/tbczhang/envs/mara`.
- Repository root remained free of `data/`, `datasets/`, and `outputs/`.

Representative validation:

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest libs/slide_cli/tests/test_cli_contract.py -q`
- Result: `8 passed`.

Residual risk:

- Storage/dataset preflight remains mandatory before `uv`, tests, model calls,
  DocQA indexing, dataset syncs, Slurm jobs, or large downloads.
- fastscratch file quota remains a routine operational risk.

## Phase 1 - Public Runtime Contract

Status: complete, closed on 2026-06-27.

Goal: prevent Web/CLI/runtime drift.

Final conclusion:

- `MARA docqa ask/chat` converts CLI input into canonical
  `ktem.docqa.DocQARequest` before calling runtime.
- CLI/Web parity covers `planner_backend`, `verification_domain`,
  `page_image_records`, and `max_context_length`.
- CLI exposes matching options for the public request fields.
- Live quality validation showed that user-facing `mara` reasoning is better
  for explanatory answers, while benchmark output needs a separate answer-only
  prompt/policy.

Public surface:

- Affected: `MARA docqa ask/chat` options and Web request-builder field
  propagation.
- Not changed: DB schema, session shape, Gradio event chain.

Evidence:

- `/mnt/scratch/users/tbczhang/outputs/MARA/phase1_quality_validation/`

Residual risk:

- Any future DocQA public request/session/JSON field change must update
  CLI/Web/runtime parity tests.

## Phase 2 - Benchmark Protocol Engineering

Status: engineering complete; thesis freeze pending. Closed on 2026-06-27 for
protocol work.

Goal: turn a runnable framework into an explainable thesis evaluation protocol.

Final conclusion:

- User-facing answers and benchmark answers are separated.
- User side keeps explanatory `mara` prompt behavior.
- Benchmark side uses `gold_answer_v1`, `/no_think`, and answer-only policy.
- Benchmark config/CLI/manifest/artifact/summary/report support prompt policy,
  no-think mode, dataset-decision metadata, failure taxonomy, route timeout
  budget, and VLM backend-readiness metadata.
- Seven candidate dataset families completed same-seed small-sample
  `gold_answer_v1` live rerun and matched `benchmark_v1 --benchmark-no-think`
  baseline: FinanceBench, QASPER, RAGTruth, ALCE, MMDocRAG, SlideVQA, ViDoRe.
- Provisional dataset matrix exists but final thesis datasets are not frozen.
- Report score authority is fixed as external/paper-grade, local
  dataset-native, and MARA diagnostic proxy.

Public surface:

- Affected: benchmark CLI/config/manifest/prediction/retrieval trace/summary
  and report fields.
- Not changed: `MARA` / `MARA-cli` public product commands, DocQA
  request/session/DB schema, Gradio event chain, user file format.

Evidence:

- Gold-answer live rerun:
  `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_gold_answer_live/`
- Matched baseline rerun:
  `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_matched_baseline/`
- Protocol matrix:
  `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_protocol/`
- Timeout fixed rerun:
  `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_timeout_rerun_fixed_20260627/`
- VLM/ViDoRe rerun:
  `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_vlm/`
- Gap analysis:
  `/mnt/scratch/users/tbczhang/outputs/MARA/phase2_gap_analysis/phase2_gap_analysis_20260627.md`

Representative validation:

- `uv run --python 3.10 python -m pytest benchmark/tests/test_runner_route_execution.py -q`: `9 passed`.
- `uv run --python 3.10 python -m pytest benchmark/tests -q`: `238 passed`, `1 warning`.
- `uv run --python 3.10 python scripts/check_codebase_hygiene.py <changed-python-files>`: no ratchet violations.
- `uv run --python 3.10 python -m pre_commit run --files <changed-files>`: passed.

Residual risk:

- Final 2-3 thesis datasets cannot be frozen until larger reruns and failure
  analysis are complete.
- Controller/hybrid/guarded routes cannot be claimed as globally superior to
  text baseline.
- Paper-grade external evaluator is not configured in representative artifacts.

## Phase 3 - Multimodal Route Workflow

Status: architecture and workflow complete; performance and quality remain
future iterations.

Goal: make multimodal proposal claims minimally reproducible through route
workflow, health gates, evidence summaries, and engineering contracts.

Final conclusion:

- Page-image, element, hybrid/controller, and graph-scope routes have executable
  paths, health/report evidence, or explicit claim boundaries.
- This closes architecture/workflow goals, not full multimodal quality goals.
- Current evidence does not support claiming every multimodal route is superior
  to text baseline.

Completed capabilities:

- `page_image_rag_vlm` route is wired to visual retriever/VLM readiness.
- Phase 3 summary/report fields record page-image backend readiness, element
  index coverage, hybrid question-type metrics, and graph scope.
- Slurm/runbook entry checks or starts 8000/8001/8002/8003 within allocation.
- Element route has an engineering contract: document metadata can become
  request-level `element_index_records`; DocQA file index can persist sidecar
  OCR/layout records; coverage report JSON/Markdown and fixture-level tests
  exist.
- GraphRAG claim is limited to local lightweight graph route with
  `full_graphrag_claim=false`.

Evidence:

- Slurm run `9294899`: 20 examples x 5 routes = 100 predictions, no skipped
  routes.
- Artifact:
  `/mnt/scratch/users/tbczhang/outputs/MARA/phase3_multimodal_slurm/20260628_045247_phase3-slidevqa-multimodal-slurm-9294899`
- Page-image route in that run: F1/native `0.3911`, page hit `0.95`.
- Hybrid route in that run: F1/native `0.3833`, page hit `0.85`.
- Controller route in that run: F1/native `0.4161`, page hit `0.9`.
- Text and element routes in that run: F1/native `0.0056`, page hit `0.0`.
- MMDocRAG persisted element-record probe showed records can be read, but
  element quality remained below matched text baseline.

Representative validation:

- Benchmark / Phase 3 tests: `250 passed`.
- Route2 / element contract targeted run: `31 passed`.
- Hygiene and pre-commit passed for changed Python files.

Residual risk:

- Element ranker/coverage and real non-gold sidecar corpus quality remain open.
- VLM/hybrid timeout, duplicate answers, answer formatting, and inline citation
  recall/precision remain future quality work.

## Phase 4 - UI And Structural Debt Control

Status: complete, closed on 2026-06-29.

Goal: keep demo UI stable and stop `ChatPage` from absorbing new business logic.

Final conclusion:

- `ChatPage` no longer absorbs new core workflow logic.
- Major workflows were moved across responsibility boundaries.
- Gradio event-chain order is locked by contract tests.
- Broader UI failures were fixed.
- Large functions and classes targeted in Phase 4 were split into focused
  helpers or kept as justified callback-signature wrappers.

Public surface:

- Not changed: `MARA` / `MARA-cli`, CLI options, JSON keys, DB schema, DocQA
  session shape, user file format, Gradio event semantics.

Representative validation:

- Focused ktem UI/runtime tests: `56 passed, 1 warning`.
- `uv run --python 3.10 pytest tests/test_descriptive_file_names.py`: `1 passed`.
- Hygiene ratchet: no violations.
- Pre-commit: passed.

Residual risk:

- `ChatPage` remains large and still coordinates preview, DocQA state, graph
  behavior, and notebook/studio glue.
- `_render_chat_file_list_html` and `rerun_page_answer` remain slightly above
  the 80-line review trigger.
- Future UI debt work must first lock Gradio workflow/DOM/source-string
  contracts, then split by real responsibility boundaries.
