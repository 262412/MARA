---
description: Set up, inspect, or launch the packaged app runtime through MARA
argument-hint: [action]
allowed-tools: Bash(MARA:*)
---

Work with the packaged app runtime through `MARA app ...`.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

Prefer focused command wrappers when the user intent is specific:

- `MARA-app-init`
- `MARA-app-doctor`
- `MARA-app-run`

Use this umbrella entry when the workflow spans multiple app actions.
