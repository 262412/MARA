---
name: MARA-app
description: Use when the user wants packaged app setup, runtime inspection, or Web UI launch through `MARA app ...`.
version: 1.0.0
---

# MARA App

## Scope

Use this skill for packaged app setup, doctor, and launch workflows through the user-facing `MARA app ...` command group.

If `MARA` is not on `PATH`, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

## Command Set

- `MARA app init`
- `MARA app doctor`
- `MARA app run`

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `MARA-app-init`
- `MARA-app-doctor`
- `MARA-app-run`
