---
description: Index local files or URLs into the shared DocQA collection
argument-hint: [path ...]
allowed-tools: Bash(kotaemon:*)
---

Index one or more files or URLs into the shared DocQA collection.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Validate the runtime first:
   !`kotaemon docqa doctor`
2. Run:
   !`kotaemon docqa index $ARGUMENTS`
