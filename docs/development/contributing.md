# Contributing

## Environment ownership

Read [storage layout](storage-layout-contract.md) before setup or tests. The
shared primary checkout owns the canonical `.venv`; linked worktrees never
synchronize it. Preserve existing environments, real configuration and data.

The supported shared Linux setup uses local Python 3.11 and the repository's
locked uv version. `install.sh` is the only synchronizer for the canonical
environment: it uses `uv sync --frozen --no-editable --extra mara --no-dev` and
reinstalls the four distributions. Initialization and optional coding-tool
bundle installation are explicit installer actions; review the target data
directories first. Do not replace an existing `.venv` or copy over `.env`.

Routine primary-checkout commands use `uv run --no-sync --python 3.11 ...`.
Source verification uses `scripts/run_with_canonical_env.sh`, which adds the
checkout libraries to the import path without installing them editable. This
also serves linked worktrees after `scripts/check_mara_worktree_env.py check`.
An overlay is source-test evidence, never installed-wheel evidence.

The installer/wrapper commands are Bash/Linux interfaces, not native Windows
setup instructions. Windows development requires an explicitly owned, already
prepared environment and the same test isolation. Do not infer that HOME is
the Windows Known Folder or resynchronize the shared environment to run a test.
Disposable CI runners use their own locked environments; their `uv sync`
commands are not permission to synchronize a developer's canonical environment.

## Verification

DocQA integration tests require an isolated Qdrant service. CI starts one with
`scripts/prepare_qdrant_test_service.py`; locally, use a new owned `--root` and
an existing pinned `--archive` to avoid downloading the binary again. The helper
prints its loopback URL and records the owned process in `process.json`.
Set `MARA_TEST_QDRANT_URL` to that URL and `MARA_TEST_QDRANT_API_KEY` to the
helper's synthetic `mara-owned-synthetic-test` key before running the suites.
These variables identify a disposable test service, separate from the real
application database. Stop that owned process when verification is finished.

Run these Bash commands from the repository root after the storage/environment
checks and with development tools already available in the owned environment:

```bash
scripts/run_with_canonical_env.sh -m pytest -q libs/slide_cli/tests
scripts/run_with_canonical_env.sh -m pytest -q libs/kotaemon/tests
scripts/run_with_canonical_env.sh -m pytest -q libs/ktem/ktem_tests
scripts/run_with_canonical_env.sh -m pytest -q benchmark/tests tests
scripts/run_with_canonical_env.sh scripts/check_pytest_collection.py --minimum 1260
scripts/run_with_canonical_env.sh scripts/check_codebase_hygiene.py
```

Choose the affected suite first. Root `conftest.py` activates the owned runtime
before business imports; subprocess fixtures must preserve that isolation.
Never run a configuration-writing example against a real user profile for a
test. Unified collection is a gate, not proof that the collected tests passed
on every OS. Native Windows limitations are described in the
[refactor status](refactor-status.md).

The [Quality workflow](../../.github/workflows/quality-gates.yaml) is the current
authority for complete hooks/static, package suites, frontend security checks,
collection, four-distribution builds, fresh wheel installs and coverage.
It uses `uv.lock`, fixed tool versions and pinned actions. The former advice
to bump `__init__.py` or add `[ignore cache]` to refresh CI environments does not
apply. Dependency changes require the existing lock/security review; do not
alter locks, scan scope, baselines or thresholds as a testing workaround.

For Desktop, use the already prepared Node environment in `apps/desktop`:
`npm run verify`. The [native workflow](../../.github/workflows/desktop-gate2.yaml)
separately builds and exercises frozen Sidecar/Electron combinations. Source
tests do not prove an installer, clean VM, macOS or unfinished product feature.

## Responsibilities and review

- `slide_cli` owns the public shell and compatibility entrypoints.
- `kotaemon` owns reusable model, agent, storage and coding-tool bundle services.
- `ktem` owns Web/DocQA composition; `ktem_contracts` holds neutral shared rules.
- `benchmark` owns experiment execution/scoring contracts; passing synthetic
  fixtures does not establish provider or research quality.
- The root `mara-app` distribution composes the runtime packages.

See [architecture contracts](architecture-contracts.md) for precise seams and
consumer tests, and [hygiene](codebase-hygiene-contract.md) for unchanged risk
and complexity gates. Pull requests should state the affected public surface,
old/new behavior, actual commands/platform/input SHA and unresolved evidence.
Report actual results in the pull request; keep lasting guidance in the existing
documentation rather than adding per-change reports.
