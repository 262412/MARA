# Slide Claude Code Profile

This profile adds focused workflows for the user-facing slide CLI.

If `slide` is not installed yet, use `pip install slide-cli` or `uv tool install slide-cli`, then run `slide doctor`.

Recommended checks:

1. slide doctor
2. slide app doctor
3. slide model providers --config modelcli.yml
4. slide model run --prompt "health check" --model ds-chat --provider openai --config modelcli.yml --dry-run
5. slide docqa doctor

Preferred DocQA entry points:

1. Use `slide-docqa-ask` for one-shot QA.
2. Use `slide-docqa-index` to ingest documents.
3. Use `slide-docqa-chat` and `slide-docqa-resume` for multi-turn sessions.
4. Use `slide-docqa-doctor` for health checks.
5. Use the umbrella `slide-docqa` workflow when the task spans multiple DocQA actions.

Preferred model routing entry points:

1. Use `slide-model-init-config` to generate a config.
2. Use `slide-model-providers` to inspect provider availability.
3. Use `slide-model-run` for one routed call, usually with `--dry-run` first.
4. Use the umbrella `slide-model` workflow when the task spans multiple model routing actions.

Preferred packaged app entry points:

1. Use `slide-app-init` to bootstrap user config.
2. Use `slide-app-doctor` to inspect runtime health.
3. Use `slide-app-run` to launch the packaged Web UI.
4. Use the umbrella `slide-app` workflow when the task spans multiple app actions.

Preferred platform support entry points:

1. Use `slide-platform-list` to inspect supported platforms.
2. Use `slide-platform-install` to install Codex or Claude Code support assets.
3. Use `slide-platform-status` to inspect installed assets.
4. Use `slide-platform-validate` before publishing or after install.
5. Use the umbrella `slide-platform` workflow when the task spans multiple platform actions.

Preferred slide entry points:

1. Use `slide` for top-level slide/deck/workspace workflows.
2. Use focused `slide-*` commands for narrow top-level actions such as `slide-review`, `slide-inspect`, `slide-write`, `slide-delete`, and `slide-shell`.
3. Confirm intent before high-permission actions that mutate files or run shell commands.
4. Use `slide-docqa` for slide-owned document QA workflows.
5. Use focused `slide-docqa-*` commands for narrow DocQA actions such as `slide-docqa-index`, `slide-docqa-ask`, and `slide-docqa-chat`.

If a user already maintains CLAUDE.md, merge this profile manually from CLAUDE.slide.md.
