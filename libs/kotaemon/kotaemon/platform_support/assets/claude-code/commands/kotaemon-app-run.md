---
description: Launch the packaged Kotaemon Web UI
argument-hint: [--host host] [--port port] [--share] [--no-browser]
allowed-tools: Bash(kotaemon:*)
---

Launch the packaged Web UI without requiring the source repository.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Confirm the runtime is healthy:
   !`kotaemon app doctor`
2. Run:
   !`kotaemon app run $ARGUMENTS`
