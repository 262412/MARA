---
description: Validate kotaemon modelcli setup
argument-hint: [prompt]
allowed-tools: Bash(kotaemon:*)
---

Run a quick CLI validation workflow for kotaemon model routing.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Validate provider availability:
   !`kotaemon modelcli providers --config modelcli.yml`

2. Run a dry-run route check first:
   !`kotaemon modelcli run --prompt "$ARGUMENTS" --model ds-chat --provider openai --config modelcli.yml --dry-run`

3. If dry-run succeeds, run the real call:
   !`kotaemon modelcli run --prompt "$ARGUMENTS" --model ds-chat --provider openai --config modelcli.yml`

If any step fails, report the exact failing step and suggest the fix.
