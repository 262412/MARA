---
description: Install, inspect, or validate Codex and Claude Code support assets through MARA
argument-hint: [platform task]
allowed-tools: Bash(MARA:*)
---

Run a platform support workflow through `MARA platform ...`.

If `MARA` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

Prefer focused command wrappers when the user intent is specific:

- `MARA-platform-list`
- `MARA-platform-status`
- `MARA-platform-install`
- `MARA-platform-validate`

Use this umbrella entry when the workflow spans multiple platform actions.
