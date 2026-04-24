---
description: Run one routed model completion through slide
argument-hint: --prompt "..." --model <name> [--provider provider] [--dry-run]
allowed-tools: Bash(slide:*)
---

Run one routed model completion.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Prefer validating routes first:
   !`slide model run $ARGUMENTS --dry-run`
2. If the route looks correct and the user wants a real call, run:
   !`slide model run $ARGUMENTS`
