---
description: Resume a saved DocQA conversation in the REPL
argument-hint: <conversation-id>
allowed-tools: Bash(kotaemon:*)
---

Resume a saved DocQA conversation in the REPL.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. If the conversation id is unknown, list sessions first:
   !`kotaemon docqa sessions`
2. Resume:
   !`kotaemon docqa resume $ARGUMENTS`
