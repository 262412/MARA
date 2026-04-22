# Slide CLI Phase 3 Docs Framing Plan

> **For agentic workers:** This file records the approved phase-3 documentation framing. Keep the owned docs aligned on the same two-line model and avoid adding a third product line.

**Goal:** Describe `slide-cli` as a two-line shell: top-level `slide ...` is the high-permission product line for runtime commands and workspace operations, including `slide apply`, `slide export-pdf`, `slide review`, and the read-only deck-observability commands `slide inspect`, `slide read-slide`, `slide extract`, and `slide search`, and `slide docqa ...` is the specialist DocQA line.

**Architecture:** Keep the existing runtime intact and explain it with the approved phase-3 language only. The docs should present `slide ...` as the product shell for runtime commands and workspace operations, including `slide apply`, `slide export-pdf`, `slide review`, and the canonical read-only deck-observability commands `slide inspect`, `slide read-slide`, `slide extract`, and `slide search`, and `slide docqa ...` as the focused specialist surface.

**Tech Stack:** Markdown docs, repo-level README updates, release guidance, and plan-file tracking.

## Files Covered

- `D:\PythonProject\kotaemon\README.md`
- `D:\PythonProject\kotaemon\libs\slide_cli\README.md`
- `D:\PythonProject\kotaemon\docs\slide_cli_release.md`
- `D:\PythonProject\kotaemon\docs\superpowers\plans\2026-04-22-slide-cli-phase3-foundation.md`

## Approved Framing

Use this exact model in future edits:

```text
slide ...        high-permission product line
slide docqa ...  specialist DocQA line
```

The canonical top-level commands currently are:

- `slide apply`
- `slide export-pdf`
- `slide review`
- `slide doctor`
- `slide run`
- `slide chat`
- `slide sessions`
- `slide resume`
- `slide inspect`
- `slide read-slide`
- `slide extract`
- `slide search`
- `slide files`
- `slide read`
- `slide write`
- `slide delete`
- `slide shell`

`slide inspect`, `slide read-slide`, `slide extract`, and `slide search` are the canonical read-only deck-observability commands on the top-level line, while `slide docqa ...` stays the specialist DocQA line.

## Guardrails

- Do not introduce a third product line in the owned documentation.
- Keep the repository README, package README, and release doc aligned on the same split.
- If the shell grows new top-level capabilities later, describe them as part of `slide ...` rather than inventing a new domain line.
