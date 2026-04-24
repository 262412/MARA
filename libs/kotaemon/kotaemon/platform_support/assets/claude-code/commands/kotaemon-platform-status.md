---
description: Inspect installed Codex or Claude Code platform support assets
argument-hint: --platform <codex|claude-code> [--target-dir path]
allowed-tools: Bash(kotaemon:*)
---

Inspect installed platform support assets.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

Run:
!`kotaemon platform status $ARGUMENTS`
