---
description: Install Codex or Claude Code support assets through MARA
argument-hint: --platform <codex|claude-code> [--mode minimal|full]
allowed-tools: Bash(MARA:*)
---

Install platform support assets.

If `MARA` is not available, install the standalone CLI first:

- `pip install mara-research-cli`
- or `uv tool install mara-research-cli`

Run:
!`MARA platform install $ARGUMENTS --yes`
