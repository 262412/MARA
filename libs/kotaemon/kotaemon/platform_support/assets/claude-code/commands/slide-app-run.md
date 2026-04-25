---
description: Launch the packaged Web UI through slide
argument-hint: [run args]
allowed-tools: Bash(slide:*)
---

Launch the packaged Web UI.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide app doctor`
2. Run:
   !`slide app run $ARGUMENTS`
