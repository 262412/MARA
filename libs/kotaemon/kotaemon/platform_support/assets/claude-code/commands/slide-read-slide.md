---
description: Read slide content and metadata
argument-hint: [deck path] [slide args]
allowed-tools: Bash(slide:*)
---

Read slide content and metadata.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Run:
   !`slide read-slide $ARGUMENTS`
