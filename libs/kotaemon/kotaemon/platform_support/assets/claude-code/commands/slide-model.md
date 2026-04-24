---
description: Run shared model routing workflows through slide
argument-hint: [model task]
allowed-tools: Bash(slide:*)
---

Run shared model routing workflows through `slide model ...`.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

Prefer focused command wrappers when the user intent is specific:

- `slide-model-init-config`
- `slide-model-providers`
- `slide-model-run`

Use `slide-model-run` with `--dry-run` before real network calls.
