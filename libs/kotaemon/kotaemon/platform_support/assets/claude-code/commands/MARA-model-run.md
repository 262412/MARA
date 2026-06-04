---
description: Run one routed model completion through MARA
argument-hint: --prompt "..." --model <name> [--provider provider] [--dry-run]
allowed-tools: Bash(MARA:*)
---

Run one routed model completion.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Prefer validating routes first:
   !`MARA model run $ARGUMENTS --dry-run`
2. If the route looks correct and the user wants a real call, run:
   !`MARA model run $ARGUMENTS`
