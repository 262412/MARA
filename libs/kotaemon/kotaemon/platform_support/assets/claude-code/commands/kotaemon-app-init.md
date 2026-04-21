---
description: Initialize the packaged app user config directory
argument-hint: [--force] [--json]
allowed-tools: Bash(kotaemon:*)
---

Initialize the packaged user config directory with editable templates.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Run:
   !`kotaemon app init $ARGUMENTS`
