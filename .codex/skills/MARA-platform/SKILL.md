---
name: MARA-platform
description: Use when the user wants to install, inspect, or validate Codex and Claude Code platform support assets through `MARA platform ...`.
version: 1.0.0
---

# MARA Platform

## Scope

Use this skill for Codex and Claude Code support asset workflows through the user-facing `MARA platform ...` command group.

If `MARA` is not on `PATH`, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

## Command Set

- `MARA platform list`
- `MARA platform status --platform codex`
- `MARA platform status --platform claude-code`
- `MARA platform install --platform codex --mode full --yes`
- `MARA platform install --platform claude-code --mode full --yes`
- `MARA platform validate`
- `MARA platform validate --platform codex --installed`
- `MARA platform validate --platform claude-code --installed`

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `MARA-platform-list`
- `MARA-platform-status`
- `MARA-platform-install`
- `MARA-platform-validate`
