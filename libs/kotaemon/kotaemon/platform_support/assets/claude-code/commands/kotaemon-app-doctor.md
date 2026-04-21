---
description: Inspect packaged app runtime health and active paths
argument-hint: [--json]
allowed-tools: Bash(kotaemon:*)
---

Inspect packaged runtime settings, app data paths, and DocQA readiness.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Run:
   !`kotaemon app doctor $ARGUMENTS`
