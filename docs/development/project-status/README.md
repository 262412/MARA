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
readiness hooks. The remaining work is research-result stability: final
dataset/route/evaluator freeze, larger reruns, VLM/element quality evidence,
citation/claim attribution analysis, and any true paper-grade external
evaluator run.
