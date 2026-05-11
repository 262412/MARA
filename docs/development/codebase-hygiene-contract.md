# Codebase Hygiene Contract

This contract is the default engineering rule set for future development in
this repository. Its purpose is to keep the codebase extensible while preventing
new "big ball of mud" growth.

## Current Risk Assessment

The risk has decreased, but it is not low.

What improved:

- `slide` / `slide-cli` now has explicit public CLI contract tests.
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
- DocQA entrypoints are split across `ktem`, `kotaemon`, and `slide_cli`, so
  behavior drift is still possible.
- Broad `except Exception` hotspots remain in preview, DocQA, office conversion,
  and CLI code. These are acceptable only when they preserve user-facing
  workflows and emit actionable diagnostics.

## Product Priority

`slide` is the public product line.

Every future change must preserve:

- `slide --help`
- `slide doctor`
- `slide run`
- `slide chat`
- `slide inspect`, `read-slide`, `extract`, `search`, `review`, `export-pdf`
- `slide files`, `read`, `write`, `delete`, `shell`
- `slide docqa ...`
- `slide app ...`
- `slide model ...`
- `slide platform ...`

If there is a conflict between preserving `slide` behavior and simplifying an
internal compatibility path, preserve `slide` first and document the tradeoff.

## Required Development Workflow

Use this workflow for every non-trivial change.

1. Identify the public surface.

   State which user-visible commands, APIs, DB tables, files, or UI events may
   be affected. If `slide` may be affected, start by running or adding
   `slide_cli` contract tests.

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

These budgets are soft limits. Crossing them is allowed only with a short
explanation and follow-up task.

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

## Boundary Rules

### `slide_cli`

- `slide_cli` is the public shell.
- Keep heavy imports lazy. Importing `slide_cli.cli` must not initialize DocQA,
  app runtime, LLMs, PDF parsing, or NLTK downloads.
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
- `slide docqa ...` and compatibility CLIs may wrap the shared behavior, but
  must not diverge silently.

## Required Verification Gates

Run the gates that match the changed files.

Always for changed Python files:

```powershell
uv run pre-commit run --files <changed-files>
```

For the public slide CLI:

```powershell
uv run --python 3.10 python -m pytest -q
```

Run from:

```powershell
D:\PythonProject\kotaemon\libs\slide_cli
```

For the GitHub Actions unit-test path:

```powershell
uv run --python 3.10 python -m pytest -q
```

Run from:

```powershell
D:\PythonProject\kotaemon\libs\kotaemon
```

For knowledge graph changes:

```powershell
uv run --python 3.10 python -m pytest libs/ktem/ktem_tests/test_knowledge_graph_service.py libs/ktem/ktem_tests/test_chat_knowledge_graph_bindings.py -q
```

For file index UI/event changes:

```powershell
uv run --python 3.10 python -m pytest libs/ktem/ktem_tests/test_file_index_page_extraction.py -q
```

For MCP / agent tool changes:

```powershell
uv run --python 3.10 python -m pytest libs/kotaemon/tests/test_mcp_tools.py libs/kotaemon/tests/test_mcp_manager.py -q
```

Do not use repository-root `pytest -q` as the default readiness signal until
the existing root collection conflicts are fixed.

## Review Checklist

Before merging, answer these questions:

- Did this change preserve the `slide` public command surface?
- Did every moved behavior have characterization coverage?
- Did the change avoid adding new eager imports?
- Did the change avoid growing existing large functions or classes?
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

- A `slide` contract test fails.
- A Gradio event chain changes order without an intentional behavior note.
- A CLI option, JSON key, DB schema, or persisted session shape changes.
- A refactor requires deleting dynamic/public-looking methods without call-site
  proof.
- A package-level gate fails for a reason unrelated to the intended change.

When in doubt, preserve behavior and add a follow-up cleanup task instead of
guessing.
