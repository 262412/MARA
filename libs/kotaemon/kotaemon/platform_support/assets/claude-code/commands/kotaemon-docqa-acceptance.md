---
description: Run the end-to-end DocQA acceptance matrix
argument-hint: [--keep-artifacts] [--verbose] [--json]
allowed-tools: Bash(kotaemon:*)
---

Run the end-to-end DocQA acceptance matrix.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Run:
   !`kotaemon docqa acceptance $ARGUMENTS`
