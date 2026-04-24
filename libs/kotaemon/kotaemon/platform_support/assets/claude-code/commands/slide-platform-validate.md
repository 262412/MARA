---
description: Validate source or installed Codex and Claude Code support assets through slide
argument-hint: [--platform <codex|claude-code>] [--installed]
allowed-tools: Bash(slide:*)
---

Validate platform support assets.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate source bundles before publishing:
   !`slide platform validate $ARGUMENTS`
2. Validate installed targets after install:
   !`slide platform validate $ARGUMENTS --installed`

