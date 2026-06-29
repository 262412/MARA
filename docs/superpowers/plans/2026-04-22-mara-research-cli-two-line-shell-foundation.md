# MARA CLI Phase 3 Docs Framing Plan

> **For agentic workers:** This file records the approved phase-3 documentation framing. Keep the owned docs aligned on the same two-line model and avoid adding a third product line.

**Goal:** Describe `MARA` as a two-line shell: top-level `MARA ...` is the high-permission product line for runtime commands and workspace operations, including `MARA apply`, `MARA export-pdf`, `MARA review`, and the read-only deck-observability commands `MARA inspect`, `MARA read-slide`, `MARA extract`, and `MARA search`, and `MARA docqa ...` is the specialist DocQA line.

**Architecture:** Keep the existing runtime intact and explain it with the approved phase-3 language only. The docs should present `MARA ...` as the product shell for runtime commands and workspace operations, including `MARA apply`, `MARA export-pdf`, `MARA review`, and the canonical read-only deck-observability commands `MARA inspect`, `MARA read-slide`, `MARA extract`, and `MARA search`, and `MARA docqa ...` as the focused specialist surface.

**Tech Stack:** Markdown docs, repo-level README updates, release guidance, and plan-file tracking.

## Files Covered

- `D:\PythonProject\kotaemon\README.md`
- `D:\PythonProject\kotaemon\libs\slide_cli\README.md`
- `D:\PythonProject\kotaemon\docs\mara_research_cli_release.md`
- `D:\PythonProject\kotaemon\docs\superpowers\plans\2026-04-22-mara-research-cli-two-line-shell-foundation.md`

## Approved Framing

Use this exact model in future edits:

```text
MARA ...        high-permission product line
MARA docqa ...  specialist DocQA line
```

The canonical top-level commands currently are:

- `MARA apply`
- `MARA export-pdf`
- `MARA review`
- `MARA doctor`
- `MARA run`
- `MARA chat`
- `MARA sessions`
- `MARA resume`
- `MARA inspect`
- `MARA read-slide`
- `MARA extract`
- `MARA search`
- `MARA files`
- `MARA read`
- `MARA write`
- `MARA delete`
- `MARA shell`

`MARA inspect`, `MARA read-slide`, `MARA extract`, and `MARA search` are the canonical read-only deck-observability commands on the top-level line, while `MARA docqa ...` stays the specialist DocQA line.

## Guardrails

- Do not introduce a third product line in the owned documentation.
- Keep the repository README, package README, and release doc aligned on the same split.
- If the shell grows new top-level capabilities later, describe them as part of `MARA ...` rather than inventing a new domain line.
