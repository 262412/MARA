---
description: Install, inspect, or validate Codex and Claude Code platform support assets
argument-hint: [platform task]
allowed-tools: Bash(kotaemon:*)
---

Run a Kotaemon platform support workflow.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

Prefer focused command wrappers when the user intent is specific:

- `kotaemon-platform-list`
- `kotaemon-platform-status`
- `kotaemon-platform-install`
- `kotaemon-platform-validate`

Common commands:

1. List supported platforms:
   !`kotaemon platform list`
2. Install Codex support:
   !`kotaemon platform install --platform codex --mode full --yes`
3. Install Claude Code support:
   !`kotaemon platform install --platform claude-code --mode full --yes`
4. Validate source bundles:
   !`kotaemon platform validate`
