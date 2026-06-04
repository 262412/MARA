---
name: MARA-model-run
description: Use when the user wants one routed model completion through `MARA model run`.
version: 1.0.0
---

# MARA Model Run

## Scope

Use this skill to run one routed completion through the `MARA` product CLI.

## Command

- `MARA model run --prompt "..." --model <name> --provider <provider> --config modelcli.yml --dry-run`
- `MARA model run --prompt "..." --model <name> --provider <provider> --config modelcli.yml`

## Focus

Prefer `--dry-run` first for new model aliases, providers, or config files.
