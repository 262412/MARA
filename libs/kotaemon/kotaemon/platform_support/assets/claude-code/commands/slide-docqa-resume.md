---
description: Resume a saved slide DocQA conversation
argument-hint: [conversation id]
allowed-tools: Bash(slide:*)
---

Resume a saved slide DocQA conversation.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Inspect sessions if no id is provided:
   !`slide docqa sessions`
2. Run:
   !`slide docqa resume $ARGUMENTS`
