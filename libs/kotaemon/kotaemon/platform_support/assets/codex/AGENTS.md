# Kotaemon Codex Agent Profile

Session discipline:
1. Validate environment and config before running model calls.
2. Prefer dry-run first for new model aliases or provider routes.
3. Use `$kotaemon-docqa` or `kotaemon docqa ...` for document QA, indexing, and session recovery.
4. Record command, exit code, and remediation on errors.
5. Avoid destructive shell commands unless user explicitly requests.
