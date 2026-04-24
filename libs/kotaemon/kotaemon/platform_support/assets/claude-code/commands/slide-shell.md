---
description: Run shell commands through the top-level slide CLI
argument-hint: [command]
allowed-tools: Bash(slide:*)
---

Run a shell command through `slide shell`.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Confirm high-risk shell actions with the user before running them.
2. Validate the runtime first:
   !`slide doctor`
3. Run:
   !`slide shell $ARGUMENTS`
