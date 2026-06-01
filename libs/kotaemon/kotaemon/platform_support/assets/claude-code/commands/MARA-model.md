---
description: Run shared model routing workflows through MARA
argument-hint: [model task]
allowed-tools: Bash(MARA:*)
---

Run shared model routing workflows through `MARA model ...`.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

Prefer focused command wrappers when the user intent is specific:

- `MARA-model-init-config`
- `MARA-model-providers`
- `MARA-model-run`

Use `MARA-model-run` with `--dry-run` before real network calls.
