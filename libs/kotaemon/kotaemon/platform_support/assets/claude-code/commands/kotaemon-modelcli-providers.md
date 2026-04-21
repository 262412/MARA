---
description: List modelcli provider availability
argument-hint: [--config path]
allowed-tools: Bash(kotaemon:*)
---

List model routing provider availability.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Run:
   !`kotaemon modelcli providers $ARGUMENTS`
