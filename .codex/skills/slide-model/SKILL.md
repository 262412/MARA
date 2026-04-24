---
name: slide-model
description: Use when the user wants shared model routing workflows through `slide model ...`.
version: 1.0.0
---

# Slide Model

## Scope

Use this skill for model routing setup, provider inspection, and routed completions through the user-facing `slide model ...` command group.

If `slide` is not on `PATH`, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

## Command Set

- `slide model init-config --output modelcli.yml`
- `slide model providers --config modelcli.yml`
- `slide model run --prompt "..." --model <name> --provider <provider> --config modelcli.yml --dry-run`
- `slide model run --prompt "..." --model <name> --provider <provider> --config modelcli.yml`

## Focused Action Skills

Prefer these focused skills when the user intent is narrow:

- `slide-model-init-config`
- `slide-model-providers`
- `slide-model-run`

