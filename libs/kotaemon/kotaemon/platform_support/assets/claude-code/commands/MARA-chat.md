---
description: Start an interactive top-level MARA chat session
argument-hint: [chat args]
allowed-tools: Bash(MARA:*)
---

Start or continue top-level MARA chat.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA chat $ARGUMENTS`
