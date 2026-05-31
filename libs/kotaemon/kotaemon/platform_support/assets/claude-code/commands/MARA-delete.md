---
description: Delete workspace files through the top-level MARA CLI
argument-hint: [path ...]
allowed-tools: Bash(MARA:*)
---

Delete workspace files through `MARA delete`.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Confirm the target paths with the user before destructive deletion.
2. Validate the runtime first:
   !`MARA doctor`
3. Run:
   !`MARA delete $ARGUMENTS`
