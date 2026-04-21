---
description: Validate DocQA runtime health
argument-hint: [--json]
allowed-tools: Bash(kotaemon:*)
---

Validate DocQA runtime health.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Run:
   !`kotaemon docqa doctor $ARGUMENTS`
