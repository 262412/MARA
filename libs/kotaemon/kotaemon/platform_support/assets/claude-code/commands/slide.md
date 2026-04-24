---
description: Run the top-level slide CLI workflow
argument-hint: [task]
allowed-tools: Bash(slide:*)
---

Run a slide workflow through the top-level CLI.

If `slide` is not available, install the standalone CLI first:

- `pip install slide-cli`
- or `uv tool install slide-cli`

1. Validate the runtime first:
   !`slide doctor`
2. Use this umbrella command when the task spans multiple top-level slide actions.
3. Prefer focused command wrappers when the user intent is specific:
   - `slide-doctor`
   - `slide-inspect`
   - `slide-review`
   - `slide-run`
   - `slide-apply`
   - `slide-export-pdf`
   - `slide-chat`
   - `slide-sessions`
   - `slide-resume`
   - `slide-files`
   - `slide-read`
   - `slide-read-slide`
   - `slide-extract`
   - `slide-search`
   - `slide-write`
   - `slide-delete`
   - `slide-shell`
4. Use `slide-docqa` and its focused wrappers for document QA work.
