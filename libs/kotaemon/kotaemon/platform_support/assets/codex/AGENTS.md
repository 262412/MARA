# Kotaemon Codex Agent Profile

Session discipline: 0. If `kotaemon` is missing, install the packaged runtime with `pip install kotaemon-app` or `uv tool install kotaemon-app`, then run `kotaemon app init` and `kotaemon app doctor`.

1. Validate environment and config before running model calls.
2. Prefer focused modelcli skills when the user intent is specific:
   - `$kotaemon-modelcli-init-config`
   - `$kotaemon-modelcli-providers`
   - `$kotaemon-modelcli-run`
3. Use `$kotaemon-modelcli` or `kotaemon modelcli ...` for shared routing workflows, and keep `$kotaemon-cli-operations` for promptui or benchmark verification.
4. Prefer focused app skills when the user intent is specific:
   - `$kotaemon-app-init`
   - `$kotaemon-app-doctor`
   - `$kotaemon-app-run`
5. Use `$kotaemon-app` or `kotaemon app ...` when the user needs setup, inspection, and launch in one workflow.
6. Prefer focused DocQA skills when the user intent is specific:
   - `$kotaemon-docqa-ask` for one-shot QA
   - `$kotaemon-docqa-index` for ingest
   - `$kotaemon-docqa-chat` / `$kotaemon-docqa-resume` for multi-turn work
   - `$kotaemon-docqa-doctor` / `$kotaemon-docqa-acceptance` for health checks
7. Use `$kotaemon-docqa` or `kotaemon docqa ...` when the user needs the full DocQA command surface or mixed workflows.
8. Record command, exit code, and remediation on errors.
9. Avoid destructive shell commands unless user explicitly requests.
