---
description: Read slide content and metadata
argument-hint: [deck path] [slide args]
allowed-tools: Bash(MARA:*)
---

Read slide content and metadata.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`MARA doctor`
2. Run:
   !`MARA read-slide $ARGUMENTS`
