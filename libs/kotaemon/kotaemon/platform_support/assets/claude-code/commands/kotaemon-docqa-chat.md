---
description: Start an interactive DocQA chat session
argument-hint: [options]
allowed-tools: Bash(kotaemon:*)
---

Start an interactive DocQA chat session.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Validate the runtime first:
   !`kotaemon docqa doctor`
2. Start the REPL:
   !`kotaemon docqa chat $ARGUMENTS`
