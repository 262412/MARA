# MARA Project Status

This directory is the canonical entry point for proposal alignment, phase
closure, thesis claim boundaries, evaluation protocol, and remaining risks.

Use these documents by role:

| Document                                      | Role                                                                       | Authority                     |
| --------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------- |
| [Current Audit](current-audit.md)             | Current project status against the proposal                                | Canonical status source       |
| [Phase Closures](phase-closures.md)           | Final Phase 0-4 conclusions and evidence pointers                          | Canonical phase summary       |
| [Claim Boundaries](claim-boundaries.md)       | Dissertation and proposal-facing claim limits                              | Canonical claim source        |
| [Evaluation Protocol](evaluation-protocol.md) | Route matrix and evaluator authority freeze draft                          | Canonical protocol draft      |
| [Residual Risks](residual-risks.md)           | Items still requiring benchmark evidence, paper results, or demo rehearsal | Canonical remaining-work list |
| [Archive](archive/README.md)                  | Historical implementation plan index and provenance notes                  | Historical only               |

Related documents such as proposal drafts, thesis MVP scope, benchmark README,
release-flow notes, superpowers plans, and superpowers specs are indexed from
[Archive](archive/README.md). They remain useful references, but they are not
current completion-status sources.

## Status Rules

- Current completion status must be updated in this directory, not in scattered
  phase notes.
- Phase development notes may exist while work is active. Once a phase closes,
  keep only the final conclusion in [Phase Closures](phase-closures.md).
- Historical plans and rerun notes are evidence, not status. Use them for
  provenance only.
- Historical specs are design rationale, not current status.
- Operational documents remain separate:
  - [Codebase Hygiene Contract](../codebase-hygiene-contract.md)
  - [Storage Layout Contract](../storage-layout-contract.md)
  - [Multimodal Route Runbook](../multimodal_route_runbook.md)
- Original proposal artifacts remain source inputs, not current status sources:
  - [Proposal PDF](../../proposal_comp702.pdf)
  - [Proposal TeX](../../proposal_comp702.tex)
  - [MARA Thesis MVP](../../mara_thesis_mvp.md)

## Current One-Line Conclusion

MARA has a complete thesis-prototype engineering skeleton: local Web/CLI DocQA
runtime, typed request/response contracts, route-aware controller semantics,
evidence and verification traces, benchmark protocol engineering, multimodal
workflow plumbing, UI/structure debt control, and paper-grade evaluator
readiness hooks. The 2026-07-05 fullsystem postfix benchmark and 2026-07-07
RAGTruth prompt-budget repair evidence freeze the final claim boundary:
SlideVQA remains the primary local-adapted multimodal dataset, MMDocRAG remains
secondary visual stability evidence, RAGTruth long-prompt execution failures
are fixed at prompt-policy level and validated on the affected examples through
local Qwen direct/lexical repair reruns, and headline score authority remains
local dataset-native / adapted metrics only. Remaining work is limited to
out-of-scope or residual research evidence: paper-grade external evaluator
configuration, larger text/core promotion if needed, Element RAG quality,
calibrated guardrail/attribution evaluation, original DocQA RAGTruth route
matrix rerun once the 8002 retrieval backend is stable, and full
production-style format robustness.

## Current Final Benchmark Status

As of 2026-07-07, the current final thesis evidence roots are:

- Fullsystem postfix benchmark:
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_statistical_20260705_fullsystem_postfix`.
- Earlier required-row synthesis:
  `/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_20260702`.
- RAGTruth prompt-budget repair:
  `/mnt/scratch/users/tbczhang/outputs/MARA/ragtruth_prompt_budget_repair_20260707`.

These are execution artifacts, not replacements for this canonical status
directory.

The 2026-07-05 fullsystem postfix synthesis supersedes earlier intermediate
benchmark notes for current claim-boundary decisions. It closed the required
route-timeout issue for MMDocRAG and left only RAGTruth residual execution
errors: 3 `controller_auto`, 3 `crag_guarded`, and 5 `text_rag` errors. Those
11 errors were traced to the Qwen 4k prompt budget: long RAGTruth
`gold_answer_v1` source prompts bypassed benchmark prompt truncation and hit
the model maximum-context guard before generation.

The 2026-07-07 repair added benchmark prompt-budget truncation for long
question/retrieval-query fields and validated the fix on the five affected
RAGTruth examples with local Qwen generation:

- Direct prompt-budget repair: 5 predictions, 5 `NO_ERROR`, no maximum-context
  failures.
- Lexical text repair with retrieved evidence: 5 predictions, 5 `NO_ERROR`,
  three retrieved hits per example, no maximum-context failures.
- The original DocQA all-route repair manifest remains a backend-evidence gap,
  because the 8002 retrieval endpoint produced repeated rate-limit failures
  during the rerun. This is not the original 4096-token context failure and
  must not be reported as route-quality evidence.

The final local-adapted benchmark decision is:

- Primary thesis dataset: `slidevqa_test_shard0_multimodal`, job `9559018`,
  25 examples and four-route multimodal matrix:
  `text_rag`, `page_image_rag_vlm`, `hybrid_rag`, `controller_auto`.
- Secondary visual stability evidence:
  `mmdocrag_dev15_available_docs_multimodal`, jobs `9559019` and `9559020`,
  with GPU-ColVision / 8k VLM settings, plus text baseline diagnostic job
  `9559021`.
- Text/core datasets, including FinanceBench, QASPER, ALCE, and RAGTruth,
  remain supporting diagnostics unless promoted by larger matched reruns.
- Evaluator authority remains `local_adapted_only_scope`; the ALCE proxy run
  is evaluator plumbing only and is not paper-grade.
- The `controller_auto` headline row must be interpreted together with
  `final_controller_route_decision_summary.md`, which records the actual
  selected internal route and route-switch behavior.
- ViDoRe remains retrieval-only diagnostic evidence.
- Element RAG, guardrail calibration, citation attribution, and format E2E are
  reported as local diagnostics with explicit residual limits.
