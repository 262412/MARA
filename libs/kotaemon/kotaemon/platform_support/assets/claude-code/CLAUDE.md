# Kotaemon Claude Code Profile

This profile adds focused workflows for kotaemon CLI operations and document QA.

If `kotaemon` is not installed yet, use `pip install kotaemon-app` or `uv tool install kotaemon-app`, then run `kotaemon app init` and `kotaemon app doctor`.

If `slide` is not installed yet, use `pip install slide-cli` or `uv tool install slide-cli`, then run `slide doctor`.

Recommended checks:

1. kotaemon modelcli providers --config modelcli.yml
2. kotaemon modelcli run --prompt "health check" --model ds-chat --provider openai --config modelcli.yml --dry-run
3. kotaemon modelcli run --prompt "health check" --model ds-chat --provider openai --config modelcli.yml
4. kotaemon docqa doctor
5. kotaemon docqa ask --prompt "What is this document about?"
6. slide doctor
7. slide docqa doctor

Preferred DocQA entry points:

1. Use `kotaemon-docqa-ask` for one-shot QA.
2. Use `kotaemon-docqa-index` to ingest documents.
3. Use `kotaemon-docqa-chat` and `kotaemon-docqa-resume` for multi-turn sessions.
4. Use `kotaemon-docqa-doctor` and `kotaemon-docqa-acceptance` for health checks.
5. Use the umbrella `kotaemon-docqa` workflow when the task spans multiple DocQA actions.

Preferred model routing entry points:

1. Use `kotaemon-modelcli-init-config` to generate a config.
2. Use `kotaemon-modelcli-providers` to inspect provider availability.
3. Use `kotaemon-modelcli-run` for one routed call, usually with `--dry-run` first.
4. Use the umbrella `kotaemon-modelcli` workflow when the task spans multiple model routing actions.

Preferred packaged app entry points:

1. Use `kotaemon-app-init` to bootstrap user config.
2. Use `kotaemon-app-doctor` to inspect runtime health.
3. Use `kotaemon-app-run` to launch the packaged Web UI.
4. Use the umbrella `kotaemon-app` workflow when the task spans multiple app actions.

Preferred slide entry points:

1. Use `slide` for top-level slide/deck/workspace workflows.
2. Use focused `slide-*` commands for narrow top-level actions such as `slide-review`, `slide-inspect`, `slide-write`, `slide-delete`, and `slide-shell`.
3. Confirm intent before high-permission actions that mutate files or run shell commands.
4. Use `slide-docqa` for slide-owned document QA workflows.
5. Use focused `slide-docqa-*` commands for narrow DocQA actions such as `slide-docqa-index`, `slide-docqa-ask`, and `slide-docqa-chat`.

If a user already maintains CLAUDE.md, merge this profile manually from CLAUDE.kotaemon.md.
