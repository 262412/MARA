---
description: Delete indexed files from the shared DocQA collection
argument-hint: <file-id-or-name ...>
allowed-tools: Bash(kotaemon:*)
---

Delete indexed files from the shared DocQA collection.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Review ids or names first when needed:
   !`kotaemon docqa files`
2. Run:
   !`kotaemon docqa delete $ARGUMENTS`
