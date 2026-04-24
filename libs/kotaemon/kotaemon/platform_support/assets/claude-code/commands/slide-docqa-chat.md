---
description: Start or continue slide DocQA chat
argument-hint: [chat args]
allowed-tools: Bash(slide:*)
---

Start or continue slide DocQA chat.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the DocQA runtime first:
   !`slide docqa doctor`
2. Run:
   !`slide docqa chat $ARGUMENTS`
