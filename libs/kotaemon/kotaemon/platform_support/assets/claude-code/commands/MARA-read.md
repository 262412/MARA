---
description: Read workspace file contents through MARA
argument-hint: [path]
allowed-tools: Bash(MARA:*)
---

Read workspace file contents.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA read $ARGUMENTS`
