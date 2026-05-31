---
description: Run shell commands through the top-level MARA CLI
argument-hint: [command]
allowed-tools: Bash(MARA:*)
---

Run a shell command through `MARA shell`.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Confirm high-risk shell actions with the user before running them.
2. Validate the runtime first:
   !`MARA doctor`
3. Run:
   !`MARA shell $ARGUMENTS`
