---
description: Resume a saved MARA DocQA conversation
argument-hint: [conversation id]
allowed-tools: Bash(MARA:*)
---

Resume a saved MARA DocQA conversation.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Inspect sessions if no id is provided:
   !`MARA docqa sessions`
2. Run:
   !`MARA docqa resume $ARGUMENTS`
