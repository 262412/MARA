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
readiness hooks. The 2026-07-01 clean Task 0-9 rerun has now closed a
local-adapted thesis evidence package: SlideVQA is the primary local-adapted
multimodal dataset, MMDocRAG is secondary visual stability evidence, and
headline score authority remains local dataset-native / adapted metrics only.
Remaining work is limited to out-of-scope or residual research evidence:
paper-grade external evaluator configuration, larger text/core promotion if
needed, Element RAG quality, calibrated guardrail/attribution evaluation, and
full production-style format robustness.

## Current Benchmark Repair Status

As of 2026-07-02, the active clean rerun root is
`/mnt/scratch/users/tbczhang/outputs/MARA/benchmark_next_20260701_task0_9_rerun`.
It is an execution artifact, not a replacement for this canonical status
directory.

Task 0-9 is closed for this clean rerun. The Task 9 synthesis artifacts are in
`09_synthesis/`, especially `task9_final_synthesis.md`,
`thesis_dataset_route_freeze_decision.md`,
`route_failure_latency_backend_table.csv`, and
`demo_preflight_checklist.md`. No Slurm job was submitted for Task 9 because
the required raw artifacts already existed and the task was synthesis plus
canonical status alignment.

The final local-adapted freeze decision is:

- Primary thesis dataset: `slidevqa_test_shard0_multimodal`, job `9469112`,
  25 examples and full multimodal route matrix.
- Secondary visual stability evidence:
  `mmdocrag_dev15_available_docs_multimodal`, jobs `9469113` and `9469114`,
  with GPU-ColVision / 8k VLM settings and zero prediction errors.
- Text/core datasets are supporting 10-smoke diagnostics in this clean rerun,
  not main thesis headline datasets.
- Task 2 is formally closed as `local_adapted_only_scope`; the ALCE proxy run
  is evaluator plumbing only and is not paper-grade.
- ViDoRe remains retrieval-only diagnostic evidence.
- Element RAG, guardrail calibration, citation attribution, and format E2E are
  reported as local diagnostics with explicit residual limits.
