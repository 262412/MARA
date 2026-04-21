---
description: Generate a default modelcli runtime config
argument-hint: [--output path] [--force]
allowed-tools: Bash(kotaemon:*)
---

Generate a default `modelcli.yml` configuration.

If `kotaemon` is not available, install the packaged runtime first:

- `pip install kotaemon-app`
- or `uv tool install kotaemon-app`
- then run `kotaemon app init`
- then run `kotaemon app doctor`

1. Run:
   !`kotaemon modelcli init-config $ARGUMENTS`
