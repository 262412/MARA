---
name: kotaemon-docqa-acceptance
description: Use this skill to run the end-to-end DocQA acceptance matrix.
version: 1.0.0
---

# Kotaemon DocQA Acceptance

## Scope

Use this skill to run the full DocQA acceptance matrix as a one-command health check.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command

- `kotaemon docqa acceptance`

## Relevant Parameters

- `--keep-artifacts` preserves temporary files and install targets
- `--verbose` surfaces low-level logs
- `--json` emits structured output

## Quality Gates

- Status is `PASS`.
- Failures include artifact paths or captured stderr for debugging.
