---
name: kotaemon-cli-operations
description: This skill should be used when the user asks to run or debug kotaemon CLI workflows for model routing, promptui, and benchmark verification.
version: 1.0.0
---

# Kotaemon CLI Operations (Codex)

Use natural-language prompts as default entrypoint.
Use explicit invocation with $kotaemon-cli-operations when deterministic handling is needed.

## Workflow

1. Confirm active virtual environment.
2. Validate providers using modelcli providers.
3. Run dry-run route check.
4. Execute real call and summarize output.
5. Record failing command with actionable fix.
