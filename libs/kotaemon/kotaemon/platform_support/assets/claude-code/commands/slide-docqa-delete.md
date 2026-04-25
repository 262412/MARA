---
description: Remove indexed files from slide DocQA
argument-hint: [file id or name ...]
allowed-tools: Bash(slide:*)
---

Remove indexed files from slide DocQA.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Confirm which indexed files should be removed.
2. Validate the DocQA runtime first:
   !`slide docqa doctor`
3. Run:
   !`slide docqa delete $ARGUMENTS`
