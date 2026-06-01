---
description: Launch the packaged Web UI through MARA
argument-hint: [run args]
allowed-tools: Bash(MARA:*)
---

Launch the packaged Web UI.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate the runtime first:
   !`MARA app doctor`
2. Run:
   !`MARA app run $ARGUMENTS`
