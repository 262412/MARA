# Historical Plan Index

Last updated: 2026-06-29.

The files below are historical implementation plans or design notes. They are
useful for provenance and for understanding why certain implementation paths
were chosen. They are not canonical status documents.

## Superpowers Plans

| File                                                                                | Historical role                                   |
| ----------------------------------------------------------------------------------- | ------------------------------------------------- |
| `docs/superpowers/plans/2026-04-22-knowledge-graph-viewer.md`                       | Knowledge graph viewer implementation plan        |
| `docs/superpowers/plans/2026-04-22-mara-research-cli-two-line-shell-foundation.md`  | Historical MARA CLI phase-3 documentation framing |
| `docs/superpowers/plans/2026-04-24-ui-visual-refresh.md`                            | UI visual refresh plan                            |
| `docs/superpowers/plans/2026-06-14-cross-dataset-benchmark-validation.md`           | Cross-dataset benchmark validation plan           |
| `docs/superpowers/plans/2026-06-14-cross-dataset-capability-validation.md`          | Cross-dataset capability validation plan          |
| `docs/superpowers/plans/2026-06-15-cross-dataset-benchmark-generalization.md`       | Cross-dataset benchmark generalization plan       |
| `docs/superpowers/plans/2026-06-15-cross-dataset-capability-reset.md`               | Cross-dataset capability reset plan               |
| `docs/superpowers/plans/2026-06-15-cross-dataset-generalization-reset.md`           | Cross-dataset generalization reset plan           |
| `docs/superpowers/plans/2026-06-15-generic-cross-dataset-benchmark-capabilities.md` | Generic cross-dataset benchmark capability plan   |

## Superpowers Specs

| File                                                                 | Historical role                         |
| -------------------------------------------------------------------- | --------------------------------------- |
| `docs/superpowers/specs/2026-04-22-knowledge-graph-viewer-design.md` | Knowledge graph viewer design rationale |
| `docs/superpowers/specs/2026-04-24-ui-visual-refresh-design.md`      | UI visual refresh design rationale      |

## Proposal, Thesis, Release, And Benchmark References

| File                                           | Role                                          | Status rule                                                             |
| ---------------------------------------------- | --------------------------------------------- | ----------------------------------------------------------------------- |
| `docs/proposal_draft.md`                       | Historical proposal draft                     | Source input only                                                       |
| `docs/proposal_draft.tex`                      | Historical proposal draft source              | Source input only                                                       |
| `docs/proposal_comp702.tex`                    | Submitted proposal source                     | Source input only                                                       |
| `docs/proposal_comp702.pdf`                    | Submitted proposal PDF                        | Source input only                                                       |
| `docs/mara_thesis_mvp.md`                      | Thesis MVP scope reference                    | Use `project-status/claim-boundaries.md` for current claims             |
| `benchmark/README.md`                          | Benchmark framework usage and field reference | Use `project-status/evaluation-protocol.md` for current score authority |
| `docs/mara_research_cli_release.md`            | Release-flow reference                        | Use `project-status/current-audit.md` for current project status        |
| `docs/development/multimodal_route_runbook.md` | Operational multimodal runbook                | Use as run instructions, not completion status                          |

## Generated Artifacts

`benchmark/artifacts/**/report.md` files are generated run outputs and are
ignored by `.gitignore`. They may be evidence for a specific run, but they are
not current project-status documents unless a conclusion is promoted into the
canonical project-status files.

## Rule

If a historical plan conflicts with a project-status document, the
project-status document wins.
