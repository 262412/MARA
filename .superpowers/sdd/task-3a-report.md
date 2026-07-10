# Task 3A Report: Server-Side Auth and Request Identity

## Status

Complete. Password mode now uses Gradio 4.39 server authentication and its
HttpOnly access-token cookies; request/SSO identity is resolved to the existing
DB user server-side before `App.user_id` is populated. All normal non-demo
launch paths pass through the shared pre-bind policy seam.

## Public surfaces

- Preserved `MARA` / `MARA-cli` names, `MARA app run` options, DB tables,
  persisted JSON/session shapes, LoginPage component attributes, public
  `onSignIn`, and subscriber order.
- Changed launch behavior intentionally: `auto`/`local` reject non-loopback
  binds; `password`/`sso` are the network modes.
- Kept local mode on DB user `default` without a LoginPage.
- Kept SSO provider logout; password logout now redirects through Gradio
  `/logout`.

## Implementation

- Added `ktem.auth.service` for DB password authentication, reset-safe legacy
  hash CAS migration, authoritative request identity, SSO user resolution, and
  read-only password-admin readiness.
- Added `LaunchConfig` / `prepare_launch()` as the single pre-bind seam. It
  resolves canonical/legacy mode, derives `KH_FEATURE_USER_MANAGEMENT`, selects
  Gradio `auth`, and rejects missing or `admin/admin` active admins with
  `MARA app init --auth-mode password` guidance.
- Removed password reads/writes/removals from browser storage. LoginPage keeps
  its attributes and event chain but ignores browser credentials.
- Removed legacy credential creation during UserManagement construction, so
  password launch does not mutate users.
- Added package-owned `ktem.sso.create_sso_app()`. Root `sso_app.py` is a thin
  wrapper; `MARA app run` and canonical/legacy container SSO launch work outside
  the source checkout through the same policy. The SSO session secret uses
  `SECRET_KEY` or a per-process cryptographic random fallback, never the known
  gradiologin default.
- Root `app.py` delegates to the packaged launcher.

## Changed files

- Runtime: `app.py`, `launch.sh`, `sso_app.py`,
  `libs/ktem/ktem/launcher.py`, `libs/ktem/ktem/sso.py`,
  `libs/ktem/ktem/runtime_defaults.py`.
- Auth/UI: `libs/ktem/ktem/auth/service.py`,
  `libs/ktem/ktem/pages/login.py`, `libs/ktem/ktem/pages/settings.py`,
  `libs/ktem/ktem/pages/resources/user.py`.
- Tests: `libs/ktem/ktem_tests/test_auth_service.py`,
  `test_auth_launcher.py`, `test_login_server_identity.py`,
  `test_sso_factory.py`, `test_runtime_defaults.py`,
  `test_auth_password_paths.py`, and `libs/kotaemon/tests/test_app_cli.py`.

## TDD evidence

### RED

- Initial auth/launcher/identity batch: exit 1, **29 failed, 14 passed**.
  Failures covered the missing auth service/pre-bind seam, browser-trusted
  identity, password storage/logout, mode-derived management, legacy mapping,
  source launcher delegation, and admin readiness.
- SSO batch: exit 1, **6 failed** for the missing package factory, root wrapper,
  packaged uvicorn dispatch, canonical container selection, and mount route.
- Launch mutation regression: exit 1, **1 failed** because UserManagement
  construction still created legacy credentials.
- SSO session-integrity regression: exit 1, **1 failed** because gradiologin's
  known default secret was still selected.

### GREEN

- Initial focused auth/runtime set: **43 passed**.
- SSO set: **6 passed**; post-secret regression: **1 passed**.
- Launch-mutation auth-service set: **13 passed**.
- Integrated ktem auth/launcher/login set: **141 passed**.
- App/CLI integration set: **23 passed**.
- Ktem keep-set: **648 passed, 5 deselected**. The five deselections are the
  pre-existing Task 6 routing/fusion/trace nodes; `test_qa.py` remains the known
  Task 6 collection blocker.
- Full `libs/slide_cli` package gate: exit 0 (114 progress nodes shown).
- Gradio/FastAPI route tests verify `/login`, HttpOnly access-token cookies,
  authoritative `/user`, `/logout` redirect/cookie deletion, and the local SSO
  `/login` mount without model services or external OAuth calls.

## Hygiene and storage

- `.venv` resolved to `/mnt/fastscratch/users/tbczhang/envs/mara`; Python
  resolved under fastscratch. Cache/runtime variables were on approved
  scratch/fastscratch paths, and the checkout had no root `data`, `datasets`,
  or `outputs`.
- Fastscratch: 292.8 GiB / 500 GiB and 430,188 / 500,000 files. Scratch:
  46.73 GiB / 2 TiB and 52,372 / 300,000 files.
- Final changed-file hygiene: no ratchet violations. Final pre-commit hooks
  passed (Black, isort, flake8, autoflake, mypy, credential/key scans, and
  codespell). `git diff --check` passed.
- `scripts/codebase_hygiene_baseline.json` was not changed. New production
  modules/functions remain within the 600/80-line budgets; there are no new
  large-code exceptions.

## Commits

- `abda836` test: define server auth hardening contracts
- `ad4328d` security: enforce server-side password identity
- `cb76ba3` test: define packaged SSO launch contract
- `197044e` security: package policy-aware SSO launch
- `bbaee08` test: follow shared app launcher boundary
- `51e3284` security: keep password launch credential read-only
- `c53cf09` security: protect SSO session integrity

## Residual risk

- A full real-browser smoke was not run because constructing the complete App
  initializes index/model dependencies. The lightweight real Gradio/FastAPI
  route tests cover the security-critical cookie/logout seams; full browser
  coverage remains appropriate for Task 4/CI.
- Deployments using multiple SSO workers or requiring sessions to survive a
  restart should set a stable high-entropy `SECRET_KEY`; the fallback is safe
  but process-local.
- The actionable password bootstrap command is specified by Task 3A, while the
  compatible CLI options themselves remain intentionally deferred to Task 3B.
- Existing Gradio/FastAPI lifecycle and pypdf ARC4 deprecation warnings remain
  unrelated dependency debt.
