---
description: Remove indexed files from MARA DocQA
argument-hint: [file id or name ...]
allowed-tools: Bash(MARA:*)
---

Remove indexed files from MARA DocQA.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Confirm which indexed files should be removed.
2. Validate the DocQA runtime first:
   !`MARA docqa doctor`
3. Run:
   !`MARA docqa delete $ARGUMENTS`
