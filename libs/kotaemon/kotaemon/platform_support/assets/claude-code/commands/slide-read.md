---
description: Read workspace file contents through slide
argument-hint: [path]
allowed-tools: Bash(slide:*)
---

Read workspace file contents.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide read $ARGUMENTS`
