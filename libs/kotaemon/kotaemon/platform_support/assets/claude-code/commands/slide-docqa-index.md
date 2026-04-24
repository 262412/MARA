---
description: Index files into slide DocQA
argument-hint: [path ...]
allowed-tools: Bash(slide:*)
---

Index files into slide DocQA.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the DocQA runtime first:
   !`slide docqa doctor`
2. Run:
   !`slide docqa index $ARGUMENTS`
