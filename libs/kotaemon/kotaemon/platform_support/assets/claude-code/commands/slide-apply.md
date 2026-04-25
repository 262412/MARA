---
description: Apply a slide patch with the top-level slide CLI
argument-hint: [patch args]
allowed-tools: Bash(slide:*)
---

Apply a slide patch.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide apply $ARGUMENTS`
