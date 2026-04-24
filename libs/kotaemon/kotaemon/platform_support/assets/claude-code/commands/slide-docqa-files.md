---
description: List indexed slide DocQA files
argument-hint: [files args]
allowed-tools: Bash(slide:*)
---

List indexed slide DocQA files.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the DocQA runtime first:
   !`slide docqa doctor`
2. Run:
   !`slide docqa files $ARGUMENTS`
