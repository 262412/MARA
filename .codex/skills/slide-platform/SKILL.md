---
name: slide-platform
description: Use when the user wants to install, inspect, or validate Codex and Claude Code platform support assets through `slide platform ...`.
version: 1.0.0
---

# Slide Platform

## Scope

Use this skill for Codex and Claude Code support asset workflows through the user-facing `slide platform ...` command group.

If `slide` is not on `PATH`, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

## Command Set

- `slide platform list`
- `slide platform status --platform codex`
- `slide platform status --platform claude-code`
- `slide platform install --platform codex --mode full --yes`
- `slide platform install --platform claude-code --mode full --yes`
- `slide platform validate`
- `slide platform validate --platform codex --installed`
- `slide platform validate --platform claude-code --installed`

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `slide-platform-list`
- `slide-platform-status`
- `slide-platform-install`
- `slide-platform-validate`
