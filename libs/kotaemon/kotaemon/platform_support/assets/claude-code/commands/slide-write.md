---
description: Create or update workspace files through slide
argument-hint: [write args]
allowed-tools: Bash(slide:*)
---

Create or update workspace files through `slide write`.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Confirm the target path and intended content before mutating files.
2. Validate the runtime first:
   !`slide doctor`
3. Run:
   !`slide write $ARGUMENTS`
