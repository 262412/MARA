---
description: Run the top-level slide agent
argument-hint: [task]
allowed-tools: Bash(MARA:*)
---

Run the top-level slide agent.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA run $ARGUMENTS`
