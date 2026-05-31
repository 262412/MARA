---
description: Create or update workspace files through MARA
argument-hint: [write args]
allowed-tools: Bash(MARA:*)
---

Create or update workspace files through `MARA write`.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Confirm the target path and intended content before mutating files.
2. Validate the runtime first:
   !`MARA doctor`
3. Run:
   !`MARA write $ARGUMENTS`
