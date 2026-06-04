---
description: Validate source or installed Codex and Claude Code support assets through MARA
argument-hint: [--platform <codex|claude-code>] [--installed]
allowed-tools: Bash(MARA:*)
---

Validate platform support assets.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

1. Validate source bundles before publishing:
   !`MARA platform validate $ARGUMENTS`
2. Validate installed targets after install:
   !`MARA platform validate $ARGUMENTS --installed`
