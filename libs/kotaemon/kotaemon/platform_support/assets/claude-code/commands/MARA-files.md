---
description: List and inspect workspace files through MARA
argument-hint: [files args]
allowed-tools: Bash(MARA:*)
---

List or inspect workspace files.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA files $ARGUMENTS`
