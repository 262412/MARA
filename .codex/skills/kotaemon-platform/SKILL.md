---
name: kotaemon-platform
description: Use when the user wants to install, inspect, or validate Codex and Claude Code platform support assets through `kotaemon platform ...`.
version: 1.0.0
---

# Kotaemon Platform

## Scope

Use this skill for platform support asset workflows that install or validate the project's Codex and Claude Code integrations.

If `kotaemon` is not on `PATH`, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

## Command Set

- `kotaemon platform list`
- `kotaemon platform status --platform codex`
- `kotaemon platform status --platform claude-code`
- `kotaemon platform install --platform codex --mode full --yes`
- `kotaemon platform install --platform claude-code --mode full --yes`
- `kotaemon platform validate`
- `kotaemon platform validate --platform codex --installed`
- `kotaemon platform validate --platform claude-code --installed`

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `kotaemon-platform-list`
- `kotaemon-platform-status`
- `kotaemon-platform-install`
- `kotaemon-platform-validate`

Use this umbrella skill when the workflow spans multiple platform actions.
