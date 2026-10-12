---
name: MARA-model-run
description: "Run one completion through MARA model routing."
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
