---
description: Run one modelcli routed completion
argument-hint: --prompt "..." --model <name> [--provider provider] [--config path] [--dry-run]
allowed-tools: Bash(kotaemon:*)
---

Run one completion through the model router.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Prefer validating routes first:
   !`kotaemon modelcli run $ARGUMENTS --dry-run`
2. If the route looks correct and the user wants a real call, run:
   !`kotaemon modelcli run $ARGUMENTS`
