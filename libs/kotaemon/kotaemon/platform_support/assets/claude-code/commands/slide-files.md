---
description: List and inspect workspace files through slide
argument-hint: [files args]
allowed-tools: Bash(slide:*)
---

List or inspect workspace files.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide files $ARGUMENTS`
