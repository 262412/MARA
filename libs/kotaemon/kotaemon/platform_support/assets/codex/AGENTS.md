# Kotaemon Codex Agent Profile

Session discipline: 0. If `kotaemon` is missing, install the packaged runtime with `pip install kotaemon-app` or `uv tool install kotaemon-app`, then run `kotaemon app init` and `kotaemon app doctor`.

1. Validate environment and config before running model calls.
2. Prefer dry-run first for new model aliases or provider routes.
3. Use `$kotaemon-cli-operations` or `kotaemon modelcli ...` for routing checks, promptui workflows, and benchmark verification.
4. Prefer focused DocQA skills when the user intent is specific:
   - `$kotaemon-docqa-ask` for one-shot QA
   - `$kotaemon-docqa-index` for ingest
   - `$kotaemon-docqa-chat` / `$kotaemon-docqa-resume` for multi-turn work
   - `$kotaemon-docqa-doctor` / `$kotaemon-docqa-acceptance` for health checks
5. Use `$kotaemon-docqa` or `kotaemon docqa ...` when the user needs the full DocQA command surface or mixed workflows.
6. Record command, exit code, and remediation on errors.
7. Avoid destructive shell commands unless user explicitly requests.
