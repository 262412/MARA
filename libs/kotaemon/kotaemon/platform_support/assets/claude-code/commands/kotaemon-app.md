---
description: Set up, inspect, or launch the packaged Kotaemon app runtime
argument-hint: [action]
allowed-tools: Bash(kotaemon:*)
---

Work with the packaged Kotaemon app runtime.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

Prefer the focused command wrappers when the user intent is specific:

- `kotaemon-app-init`
- `kotaemon-app-doctor`
- `kotaemon-app-run`

Use this umbrella entry when the workflow spans multiple app actions.
