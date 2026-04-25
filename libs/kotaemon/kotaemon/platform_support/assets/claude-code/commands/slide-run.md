---
description: Run the top-level slide agent
argument-hint: [task]
allowed-tools: Bash(slide:*)
---

Run the top-level slide agent.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide run $ARGUMENTS`
