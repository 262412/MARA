---
description: Run the top-level slide agent
argument-hint: [task]
allowed-tools: Bash(MARA:*)
---

Run the top-level slide agent.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA run $ARGUMENTS`
