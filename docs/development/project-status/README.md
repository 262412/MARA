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
readiness hooks. The 2026-07-02 final thesis benchmark required rows have now
completed and been synthesized: SlideVQA is the primary local-adapted
multimodal dataset, MMDocRAG is secondary visual stability evidence, and
headline score authority remains local dataset-native / adapted metrics only.
Remaining work is limited to out-of-scope or residual research evidence:
paper-grade external evaluator configuration, larger text/core promotion if
needed, Element RAG quality, calibrated guardrail/attribution evaluation, and
full production-style format robustness.

## Current Final Benchmark Status

As of 2026-07-03, the final thesis benchmark root is
`/mnt/scratch/users/tbczhang/outputs/MARA/final_thesis_benchmark_20260702`.
It is an execution artifact, not a replacement for this canonical status
directory.

The final required Slurm jobs completed on A100 node `gpu06` with
`COMPLETED 0:0`. The final synthesis artifacts are in `09_synthesis/`,
especially `final_benchmark_synthesis_report.md`,
`final_main_result_table.csv`,
`final_secondary_visual_stability_table.csv`,
`final_failure_latency_backend_table.csv`, and
`final_controller_route_decision_summary.md`,
`final_required_benchmark_closeout_report.md`.

The final local-adapted benchmark decision is:

- Primary thesis dataset: `slidevqa_test_shard0_multimodal`, job `9559018`,
  25 examples and four-route multimodal matrix:
  `text_rag`, `page_image_rag_vlm`, `hybrid_rag`, `controller_auto`.
- Secondary visual stability evidence:
  `mmdocrag_dev15_available_docs_multimodal`, jobs `9559019` and `9559020`,
  with GPU-ColVision / 8k VLM settings, plus text baseline diagnostic job
  `9559021`.
- Text/core datasets remain supporting 10-smoke diagnostics from the clean
  rerun, not main thesis headline datasets.
- Evaluator authority remains `local_adapted_only_scope`; the ALCE proxy run
  is evaluator plumbing only and is not paper-grade.
- The `controller_auto` headline row must be interpreted together with
  `final_controller_route_decision_summary.md`, which records the actual
  selected internal route and route-switch behavior.
- ViDoRe remains retrieval-only diagnostic evidence.
- Element RAG, guardrail calibration, citation attribution, and format E2E are
  reported as local diagnostics with explicit residual limits.
