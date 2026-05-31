---
description: Apply a slide patch with the top-level MARA CLI
argument-hint: [patch args]
allowed-tools: Bash(MARA:*)
---

Apply a slide patch.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA apply $ARGUMENTS`
