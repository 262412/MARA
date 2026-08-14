# Codebase Hygiene Contract

This contract is the default engineering rule set for future development in
this repository. Its purpose is to keep the codebase extensible while preventing
new "big ball of mud" growth.

## Current Risk Assessment

The risk has decreased, but it is not low.

What improved:

- `MARA` now has explicit public CLI contract tests.
- `KnowledgeGraphBuilder._build_canonical_graph` is no longer a single
  several-hundred-line implementation body.
- File index event registration has less repeated event-chain code.
- The GitHub Actions unit-test path for `libs/kotaemon` is green.

Remaining high-risk areas:

- `libs/ktem/ktem/pages/chat/__init__.py` still owns UI construction, event
  binding, chat runtime, file preview, DocQA state, knowledge graph refresh, and
  session behavior.
- `libs/ktem/ktem/index/file/_events.py` still has large event registration
  bodies where behavior depends on Gradio chain order.
- `libs/ktem/ktem/pages/chat/knowledge_graph_builder.py` is improved but still
  has several 130+ line helpers that should not grow further.
- DocQA entrypoints are split across `ktem`, `kotaemon`, and the MARA CLI
  implementation package (`slide_cli`), so behavior drift is still possible.
- Broad `except Exception` hotspots remain in preview, DocQA, office conversion,
  and CLI code. These are acceptable only when they preserve user-facing
  workflows and emit actionable diagnostics.

The current risk inventory is now tracked as a ratchet baseline in
`scripts/codebase_hygiene_baseline.json`. That baseline is not approval for the
existing debt; it is the line future changes must not make worse.

## Product Priority

`MARA` is the public product line. The public console entrypoints are `MARA`
and `MARA-cli`; `MARA` is canonical, and `MARA-cli` is the explicit CLI alias.

Every future change must preserve:

- `MARA --help`
- `MARA-cli --help`
- `MARA doctor`
- `MARA run`
- `MARA chat`
- `MARA inspect`, `read-slide`, `extract`, `search`, `review`, `export-pdf`
- `MARA files`, `read`, `write`, `delete`, `shell`
- `MARA docqa ...`
- `MARA app ...`
- `MARA model ...`
- `MARA platform ...`

`MARA-cli ...` must dispatch to the same command surface as `MARA ...`.

If there is a conflict between preserving `MARA` behavior and simplifying an
internal compatibility path, preserve `MARA` first and document the tradeoff.

## Required Development Workflow

Use this workflow for every non-trivial change.

0. Verify the storage layout.

   Follow `docs/development/storage-layout-contract.md` before running `uv`,
   `pip`, tests, `MARA app init`, DocQA indexing, dataset syncs, Slurm jobs,
   model downloads, or any task that may create many files.
   The primary `~/scratch/projects/MARA/.venv` must be a symlink to
   `~/fastscratch/envs/mara`; linked worktrees must use the repository `.venv`
   sentinel and `scripts/run_with_canonical_env.sh`, never the primary
   environment. Caches, Codex state, and MARA runtime data must
   stay on `fastscratch`. Important source datasets must stay in
   `~/data/datasets/MARA`, and compute-time dataset copies or outputs must stay
   in `~/scratch/datasets/MARA`, `~/scratch/outputs/MARA`, or
   `~/fastscratch/datasets/MARA` for high-I/O small-file workloads. If the
   layout is wrong or fastscratch file quota is above the soft limit, stop and
   repair the layout before continuing.

1. Identify the public surface.

   State which user-visible commands, APIs, DB tables, files, or UI events may
   be affected. If `MARA` or `MARA-cli` may be affected, start by running or
   adding MARA CLI contract tests in the internal `slide_cli` package.

2. Add characterization coverage before refactoring.

   For existing behavior, tests should lock the current behavior before moving
   code. For bug fixes, write the failing regression test before production
   changes.

3. Keep write scopes small.

   A change should normally touch one subsystem plus its tests. Avoid mixing
   feature work, cleanup, formatting, and behavior changes in the same commit.

4. Preserve names at boundaries.

   Do not rename public commands, Click options, Gradio component attributes,
   database fields, persisted JSON keys, session fields, or skill names unless
   there is a migration plan and a compatibility test.

5. Run the smallest meaningful test first.

   Use targeted tests for the changed subsystem, then run the package-level gate
   before claiming the work is ready.

6. Record residual risk.

   If code remains large, dynamic, or under-tested, say so in the PR summary.
   Do not hide risk behind a green test run.

## Complexity Budgets

These budgets are review triggers, not hard line-count targets. They must never
be used as justification to remove behavior, reduce test coverage, degrade
performance, hide data in dense literals, or make code harder to read. Prefer
clear, complete code over compact code that exists only to satisfy a number.

Crossing a budget is allowed when the larger shape is the clearest correct
implementation. Record a short explanation and a follow-up task when the size
creates real maintenance risk.

- New function: target under 80 lines.
- New class: target under 300 lines.
- New module: target under 600 lines.
- Event registration functions: split when a chain exceeds one user workflow.
- CLI command function: should parse inputs, call a service, and render output.
  It should not implement business logic directly.
- Broad exception handler: must either re-raise as a user-facing error or log
  enough context to debug the failure.

If a touched function is already above budget, do not make it larger unless the
change is a pure bug fix and a follow-up cleanup is recorded.

## Legitimate Large Code

Some code is legitimately long. Size alone is not a "big ball of mud" signal
when the code remains cohesive, readable, and well covered.

Acceptable large-code cases include:

- Generated code, protocol schemas, migration definitions, or static lookup
  tables.
- Test fixtures, expected dictionaries, golden payloads, and characterization
  data where expanded formatting is clearer than compact formatting.
- Declarative UI or configuration blocks that would become less readable if
  split mechanically.
- Performance-sensitive code where splitting creates measurable overhead or
  obscures the algorithm.
- Compatibility adapters that must preserve several external shapes in one
  audited place.

For legitimate large code:

- Keep behavior complete. Do not remove features, edge cases, validation,
  diagnostics, or tests to satisfy a line budget.
- Keep readable formatting. Do not compress dictionaries, expected payloads,
  prompts, schemas, or assertions into dense forms only to reduce line count.
- Split only at real responsibility boundaries such as parser, service,
  renderer, controller, adapter, or data definition.
- Add or preserve characterization coverage before changing behavior.
- If the budget is crossed intentionally, document why the larger shape is
  clearer or safer and record any useful follow-up cleanup.

Mechanical compliance is forbidden. Do not merge statements, hide logic in
clever comprehensions, shorten names, remove comments that explain non-obvious
behavior, or degrade performance merely to stay under a numeric budget.

## Debt Baseline And Ratchet

Use `scripts/check_codebase_hygiene.py` to keep existing debt from growing while
allowing incremental work to continue.

- Existing over-budget modules, classes, functions, and non-actionable broad
  exception handlers are recorded in `scripts/codebase_hygiene_baseline.json`.
- New Python code must meet the complexity budgets above.
- A touched item already listed in the baseline must not grow beyond its
  recorded size.
- A touched file must not increase its count of non-actionable broad exception
  handlers.
- A new broad exception handler is acceptable only when it re-raises, logs, or
  otherwise emits enough diagnostic context for a user or maintainer to act.
- Baseline updates are allowed only for intentional risk acceptance. The PR or
  commit message must state why the increase was necessary and what follow-up
  will reduce it.

To intentionally refresh the baseline after an accepted change:

```powershell
uv run --no-sync --python 3.10 python scripts/check_codebase_hygiene.py --update-baseline
```

Do not refresh the baseline just to make the gate pass.

## Risk Triage

Use this priority order when deciding what must be fixed now and what can stay
as tracked residual risk.

- P0: changes that can break the `MARA` / `MARA-cli` public command surface,
  lazy imports, Gradio event order, CLI options, JSON keys, DB schema,
  persisted session shape, or DocQA behavior parity.
- P1: changes that grow baseline debt, add new over-budget functions/classes,
  add non-actionable broad exception handling, or duplicate DocQA request/session
  behavior across entrypoints.
- P2: frontend asset size, CSS selector sprawl, `!important` growth, TODO
  cleanup, benchmark-only complexity, and test module size.

P0 issues block merge. P1 issues block merge unless explicitly accepted with a
follow-up. P2 issues should be tracked, but do not block unrelated product work.

## Boundary Rules

### MARA CLI (`slide_cli`)

- `MARA` and `MARA-cli` are the public shells. `slide_cli` is the internal
  implementation package name until the codebase itself is intentionally
  renamed.
- Keep heavy imports lazy. Importing the internal `slide_cli.cli` module must
  not initialize DocQA, app runtime, LLMs, PDF parsing, or NLTK downloads.
- Public command names, options, JSON fields, and help text require contract
  tests.
- Prefer adapter calls into shared runtime code over duplicating DocQA logic.

### `kotaemon`

- Core library code should not eagerly depend on `ktem` UI/runtime modules.
- Allow `ktem` imports only inside runtime bootstrap, CLI compatibility paths,
  or explicit app integration seams.
- Preserve `kotaemon.agents` lazy-load behavior because MCP and agent tests rely
  on it.

### `ktem`

- UI pages may coordinate services, but should not accumulate business logic.
- Gradio event order is behavior. Refactors must preserve chain order and
  component attributes.
- Long page classes should be split by workflow: UI construction, event
  registration, runtime services, rendering, and persistence.

### DocQA

- There should be one behavioral source of truth for request construction,
  file selection, scope selection, graph context, citation mode, language, and
  session persistence.
- `MARA docqa ...` and compatibility CLIs may wrap the shared behavior, but
  must not diverge silently.

## Required Verification Gates

Run the gates that match the changed files.

Always before large installs, model downloads, app initialization, DocQA
indexing, dataset syncs, Slurm jobs, or long development sessions:

```powershell
cd ~/scratch/projects/MARA
source ~/.bashrc
readlink -f .venv
readlink -f .venv/bin/python
df -h .venv ktem_app_data
printf 'PRE_COMMIT_HOME=%s\n' "$PRE_COMMIT_HOME"
printf 'UV_NO_CACHE=%s\n' "$UV_NO_CACHE"
lfs quota -h -u tbczhang /mnt/fastscratch
quota -s
test ! -e data
test ! -e datasets
test ! -e outputs
test ! -e .theflow
```

Always before changing or committing Python files:

```powershell
uv run --no-sync --python 3.10 python scripts/check_codebase_hygiene.py <changed-files>
```

Always for changed Python files:

```powershell
uv run --no-sync --python 3.10 python -m pre_commit run --files <changed-files>
```

For the public MARA CLI entrypoints:

```powershell
uv run --no-sync --python 3.10 python -m pytest -q
```

Run from:

```powershell
D:\PythonProject\MARA\libs\slide_cli
```

For the GitHub Actions unit-test path:

```powershell
uv run --no-sync --python 3.10 python -m pytest -q
```

Run from:

```powershell
D:\PythonProject\MARA\libs\kotaemon
```

For knowledge graph changes:

```powershell
uv run --no-sync --python 3.10 python -m pytest libs/ktem/ktem_tests/test_knowledge_graph_service.py libs/ktem/ktem_tests/test_chat_knowledge_graph_bindings.py -q
```

For file index UI/event changes:

```powershell
uv run --no-sync --python 3.10 python -m pytest libs/ktem/ktem_tests/test_file_index_page_extraction.py -q
```

For MCP / agent tool changes:

```powershell
uv run --no-sync --python 3.10 python -m pytest libs/kotaemon/tests/test_mcp_tools.py libs/kotaemon/tests/test_mcp_manager.py -q
```

Do not use repository-root `pytest -q` as the default readiness signal until
the existing root collection conflicts are fixed.

## Review Checklist

Before merging, answer these questions:

- Did this change preserve the `MARA` / `MARA-cli` public command surface?
- Did every moved behavior have characterization coverage?
- Did the change avoid adding new eager imports?
- Did the change avoid growing existing large functions or classes?
- Did the change avoid mechanical line-count compliance that harms behavior,
  readability, test clarity, diagnostics, or performance?
- Did the hygiene ratchet pass, or is any baseline update justified and
  documented?
- Did broad exception handling remain user-actionable?
- Did the tests run from the same working directory as CI or the relevant
  package gate?
- Is any remaining risk documented in the PR or commit message?

## Commit Rules

- Commit 1 should normally contain protection tests or characterization tests.
- Commit 2 should contain the refactor or feature.
- Avoid mixing formatting-only churn with logic changes.
- If a formatter touches unrelated lines, state that explicitly.
- Do not squash unrelated subsystems into one commit just because tests pass.

## Stop Conditions

Stop and reassess before continuing if any of these happen:

- A `MARA` or `MARA-cli` contract test fails.
- A Gradio event chain changes order without an intentional behavior note.
- A CLI option, JSON key, DB schema, or persisted session shape changes.
- A change removes behavior, compresses readable data, weakens tests, or
  degrades performance only to satisfy a line-count budget.
- A refactor requires deleting dynamic/public-looking methods without call-site
  proof.
- The hygiene ratchet fails without an intentional risk note and follow-up.
- A package-level gate fails for a reason unrelated to the intended change.

When in doubt, preserve behavior and add a follow-up cleanup task instead of
guessing.
