---
name: slide-platform-install
description: Use when the user wants to install Codex or Claude Code platform support assets through `slide platform install`.
version: 1.0.0
---

# Slide Platform Install

## Scope

Use this skill to install Codex or Claude Code support assets through the `slide` product CLI.

## Command

- `slide platform install --platform codex --mode full --yes`
- `slide platform install --platform claude-code --mode full --yes`

## Focus

Use `--mode minimal` for skills, agents, and profile docs only. Use `--mode full` when the user also wants Claude commands, hooks, scripts, and templates.

