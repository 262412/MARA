---
description: Start an interactive top-level slide chat session
argument-hint: [chat args]
allowed-tools: Bash(slide:*)
---

Start or continue top-level slide chat.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide chat $ARGUMENTS`
