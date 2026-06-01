---
description: Start or continue MARA DocQA chat
argument-hint: [chat args]
allowed-tools: Bash(MARA:*)
---

Start or continue MARA DocQA chat.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate the DocQA runtime first:
   !`MARA docqa doctor`
2. Run:
   !`MARA docqa chat $ARGUMENTS`
