---
description: List indexed MARA DocQA files
argument-hint: [files args]
allowed-tools: Bash(MARA:*)
---

List indexed MARA DocQA files.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the DocQA runtime first:
   !`MARA docqa doctor`
2. Run:
   !`MARA docqa files $ARGUMENTS`
