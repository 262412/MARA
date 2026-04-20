# Kotaemon Codex Agent Profile

Session discipline:
1. Validate environment and config before running model calls.
2. Prefer dry-run first for new model aliases or provider routes.
3. Use `$kotaemon-cli-operations` or `kotaemon modelcli ...` for routing checks, promptui workflows, and benchmark verification.
4. Use `$kotaemon-docqa` or `kotaemon docqa ...` for document QA, indexing, session recovery, and acceptance checks.
5. Record command, exit code, and remediation on errors.
6. Avoid destructive shell commands unless user explicitly requests.
