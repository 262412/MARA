---
description: Install Codex or Claude Code support assets through slide
argument-hint: --platform <codex|claude-code> [--mode minimal|full]
allowed-tools: Bash(slide:*)
---

Install platform support assets.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

Run:
!`slide platform install $ARGUMENTS --yes`

