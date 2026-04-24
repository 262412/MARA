---
name: kotaemon-platform-install
description: Use when the user wants to install Codex or Claude Code platform support assets through `kotaemon platform install`.
version: 1.0.0
---

# Kotaemon Platform Install

## Scope

Use this skill to install project platform assets into Codex or Claude Code.

## Command

- `kotaemon platform install --platform codex --mode full --yes`
- `kotaemon platform install --platform claude-code --mode full --yes`

## Focus

Use `--mode minimal` when the user only wants skills, agents, and the platform profile. Use `--mode full` when they also want commands, hooks, scripts, and templates.
