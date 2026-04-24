---
name: slide-app
description: Use when the user wants packaged app setup, runtime inspection, or Web UI launch through `slide app ...`.
version: 1.0.0
---

# Slide App

## Scope

Use this skill for packaged app setup, doctor, and launch workflows through the user-facing `slide app ...` command group.

If `slide` is not on `PATH`, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

## Command Set

- `slide app init`
- `slide app doctor`
- `slide app run`

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `slide-app-init`
- `slide-app-doctor`
- `slide-app-run`
