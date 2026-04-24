---
description: Install, inspect, or validate Codex and Claude Code support assets through slide
argument-hint: [platform task]
allowed-tools: Bash(slide:*)
---

Run a platform support workflow through `slide platform ...`.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

Prefer focused command wrappers when the user intent is specific:

- `slide-platform-list`
- `slide-platform-status`
- `slide-platform-install`
- `slide-platform-validate`

Use this umbrella entry when the workflow spans multiple platform actions.
