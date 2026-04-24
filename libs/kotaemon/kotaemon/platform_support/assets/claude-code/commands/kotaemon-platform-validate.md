---
description: Validate source or installed Codex and Claude Code platform support assets
argument-hint: [--platform <codex|claude-code>] [--installed]
allowed-tools: Bash(kotaemon:*)
---

Validate platform support assets.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Validate source bundles before publishing:
   !`kotaemon platform validate $ARGUMENTS`
2. Validate installed targets after install:
   !`kotaemon platform validate $ARGUMENTS --installed`
