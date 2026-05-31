---
description: Review a slide deck without mutating it
argument-hint: [deck path]
allowed-tools: Bash(MARA:*)
---

Review a slide deck.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA review $ARGUMENTS`
