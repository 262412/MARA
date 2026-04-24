---
description: Delete workspace files through the top-level slide CLI
argument-hint: [path ...]
allowed-tools: Bash(slide:*)
---

Delete workspace files through `slide delete`.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Confirm the target paths with the user before destructive deletion.
2. Validate the runtime first:
   !`slide doctor`
3. Run:
   !`slide delete $ARGUMENTS`
