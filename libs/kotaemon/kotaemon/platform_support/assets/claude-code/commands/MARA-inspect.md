---
description: Inspect a slide deck structure
argument-hint: [deck path]
allowed-tools: Bash(MARA:*)
---

Inspect a slide deck.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA inspect $ARGUMENTS`
