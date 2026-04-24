---
description: Run mixed Kotaemon CLI operations such as promptui, modelcli, and benchmarks
argument-hint: [task]
allowed-tools: Bash(kotaemon:*), Bash(python:*)
---

Run a mixed Kotaemon CLI operations workflow.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Prefer focused command wrappers when the user intent is specific:
   - `kotaemon-modelcli-init-config`
   - `kotaemon-modelcli-providers`
   - `kotaemon-modelcli-run`
   - `kotaemon-app-init`
   - `kotaemon-app-doctor`
   - `kotaemon-app-run`
   - `kotaemon-platform`
2. Use this umbrella command for promptui, makedoc, start-project, terminal UI, benchmark, or mixed CLI workflows.
3. For model calls, validate with dry-run before real network calls:
   !`kotaemon modelcli run $ARGUMENTS --dry-run`
4. For promptui config generation, run:
   !`kotaemon promptui export $ARGUMENTS`
5. For promptui startup, run:
   !`kotaemon promptui run $ARGUMENTS`
6. For docs or project scaffolding, use:
   !`kotaemon makedoc $ARGUMENTS`
   !`kotaemon start-project $ARGUMENTS`
