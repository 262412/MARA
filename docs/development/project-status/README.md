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

## Current Benchmark Repair Status

As of 2026-07-01, the active execution plan is
`/mnt/scratch/users/tbczhang/outputs/MARA/benchmark_next_20260629/benchmark_task_checklist.md`.
It is an execution artifact, not a replacement for this canonical status
directory.

The first 10-smoke batch produced usable text, SlideVQA, ViDoRe, and evaluator
plumbing artifacts, but it did not freeze thesis datasets/routes/evaluator
authority. Route-matrix complement jobs `9406278-9406281` are complete with
full artifacts. MMDocRAG `text_rag`/`element_rag` repair jobs `9406282-9406283`
are complete, with sparse element coverage evidence. MMDocRAG visual/controller
sanity jobs `9406284-9406286` are also complete with artifacts and no 2048
context regression. L40S fallback limit=10 rows `9408508-9408510` completed
with full artifacts, but `page_image_rag_vlm` and `hybrid_rag` still show route
timeouts plus VLM 4096-context overflows. The original H100 rows
`9408062-9408064` were cancelled before start and replaced by H100/3-GPU rows
`9413488-9413490` using `MARA_VLM_EVIDENCE_TEXT_CHARS=120`. Because H100
remained queued, L40S repaired fallback rows `9414048-9414050` were also
submitted on `gpu48` with the same prompt cap. Those rows completed, but
`page_image_rag_vlm` and `hybrid_rag` still had route timeouts plus VLM
4096-context overflows. L40S 8k-context rows `9416399-9416401` completed and
fixed VLM context overflow, but `page_image_rag_vlm` and `hybrid_rag` still
have route-timeout/performance failures. H100 8k rows `9416402-9416404` remain
pending as GPU ColVision/performance comparison. L40S timeout-budget diagnostic
rows `9426207-9426208` are submitted with route_timeout=1200 to distinguish a
too-short 600s budget from a persistent route performance blocker. The 1-7
repair plan is closed as an evidence-chain repair, but final freeze remains
blocked until timeout/performance synthesis, larger matched reruns, and failure
synthesis are updated here. The first larger matched closure jobs have now been
submitted on L40S resources: RAGTruth-50 `9426781`, ALCE-50 `9426782`, and
SlideVQA-25 `9426783`. These are pending/in-flight evidence rows, not freeze
results. Those closure jobs have since completed with full artifact four-tuples,
as have H100 MMDocRAG comparison rows `9416402-9416404` and L40S
timeout-budget rows `9426207-9426208`. The missing benchmark artifact gap is
now closed; the remaining benchmark work is final failure synthesis and the
explicit thesis dataset/route/evaluator freeze decision.
