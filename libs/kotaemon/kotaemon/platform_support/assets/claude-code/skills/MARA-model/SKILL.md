---
name: MARA-model
description: Use when the user wants shared model routing workflows through `MARA model ...`.
version: 1.0.0
---

# MARA Model

## Scope

Use this skill for model routing setup, provider inspection, and routed completions through the user-facing `MARA model ...` command group.

If `MARA` is not on `PATH`, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

## Command Set

- `MARA model init-config --output modelcli.yml`
- `MARA model providers --config modelcli.yml`
- `MARA model run --prompt "..." --model <name> --provider <provider> --config modelcli.yml --dry-run`
- `MARA model run --prompt "..." --model <name> --provider <provider> --config modelcli.yml`

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `MARA-model-init-config`
- `MARA-model-providers`
- `MARA-model-run`
