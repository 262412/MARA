# MARA CLI Safety Rules

- Validate provider availability before model invocation.
- Use dry-run for first-time route checks.
- Avoid destructive shell commands by default.
- Keep user secrets in environment variables, not committed files.
- Record exact command and exit code when reporting failures.
