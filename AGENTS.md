# MARA Agent Instructions

General coding style:

- Write clean, simple, and effective code.
- Do not add unnecessary fallbacks, defensive branches, compatibility hacks, or
  over-engineered abstractions unless they are clearly needed for the task.

Mandatory development contract:

- For every non-trivial repository change, follow
  `docs/development/codebase-hygiene-contract.md`.
- Before editing, identify the affected public surface: `MARA`, `MARA-cli`,
  DocQA behavior, Gradio event chains, persisted data, config, files, or APIs.
- Preserve the `MARA` / `MARA-cli` public command surface unless there is an
  explicit migration plan and compatibility coverage.
- Run the relevant verification gates from the hygiene contract before claiming
  a change is complete.
- Do not refresh `scripts/codebase_hygiene_baseline.json` just to make the
  hygiene gate pass.
