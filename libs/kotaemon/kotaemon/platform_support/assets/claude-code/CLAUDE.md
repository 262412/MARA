# Kotaemon Claude Code Profile

This profile adds focused workflows for kotaemon CLI operations and document QA.

If `kotaemon` is not installed yet, use `pip install kotaemon-app` or `uv tool install kotaemon-app`, then run `kotaemon app init` and `kotaemon app doctor`.

Recommended checks:

1. kotaemon modelcli providers --config modelcli.yml
2. kotaemon modelcli run --prompt "health check" --model ds-chat --provider openai --config modelcli.yml --dry-run
3. kotaemon modelcli run --prompt "health check" --model ds-chat --provider openai --config modelcli.yml
4. kotaemon docqa doctor
5. kotaemon docqa ask --prompt "What is this document about?"

If a user already maintains CLAUDE.md, merge this profile manually from CLAUDE.kotaemon.md.
