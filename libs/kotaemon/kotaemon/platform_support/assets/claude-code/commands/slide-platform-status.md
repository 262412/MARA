---
description: Inspect installed Codex or Claude Code support assets through slide
argument-hint: --platform <codex|claude-code> [--target-dir path]
allowed-tools: Bash(slide:*)
---

Inspect installed platform support assets.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

Run:
!`slide platform status $ARGUMENTS`

