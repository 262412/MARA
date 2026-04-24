---
description: Set up, inspect, or launch the packaged app runtime through slide
argument-hint: [action]
allowed-tools: Bash(slide:*)
---

Work with the packaged app runtime through `slide app ...`.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

Prefer focused command wrappers when the user intent is specific:

- `slide-app-init`
- `slide-app-doctor`
- `slide-app-run`

Use this umbrella entry when the workflow spans multiple app actions.

