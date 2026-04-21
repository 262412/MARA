---
description: List indexed files in the shared DocQA collection
argument-hint: [--json]
allowed-tools: Bash(kotaemon:*)
---

List indexed files in the shared DocQA collection.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Run:
   !`kotaemon docqa files $ARGUMENTS`
