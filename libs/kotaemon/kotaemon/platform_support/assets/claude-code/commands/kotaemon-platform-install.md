---
description: Install Codex or Claude Code platform support assets
argument-hint: --platform <codex|claude-code> [--mode minimal|full]
allowed-tools: Bash(kotaemon:*)
---

Install platform support assets.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Use `--mode minimal` for skills, agents, and profile docs only.
2. Use `--mode full` for all platform assets, including commands and hooks.
3. Run:
   !`kotaemon platform install $ARGUMENTS --yes`
