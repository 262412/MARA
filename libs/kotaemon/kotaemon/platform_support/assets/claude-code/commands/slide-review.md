---
description: Review a slide deck without mutating it
argument-hint: [deck path]
allowed-tools: Bash(slide:*)
---

Review a slide deck.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide review $ARGUMENTS`
