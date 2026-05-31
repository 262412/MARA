---
description: Resume a saved top-level slide session
argument-hint: [session id]
allowed-tools: Bash(MARA:*)
---

Resume a saved top-level slide session.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Inspect sessions if no id is provided:
   !`MARA sessions`
2. Run:
   !`MARA resume $ARGUMENTS`
