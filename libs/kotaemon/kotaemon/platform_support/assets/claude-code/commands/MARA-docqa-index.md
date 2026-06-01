---
description: Index files into MARA DocQA
argument-hint: [path ...]
allowed-tools: Bash(MARA:*)
---

Index files into MARA DocQA.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate the DocQA runtime first:
   !`MARA docqa doctor`
2. Run:
   !`MARA docqa index $ARGUMENTS`
