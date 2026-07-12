# Task 12G Completion Report

Date: 2026-07-12

Status: complete

Commit range: `d3e5d39..d8fcff8`

## Outcome

Settings, user-administration, Resources visibility, and issue-report callbacks
now derive managed-mode identity from the injected server request. Browser or
Gradio State remains only the existing local/auto fallback. A shared
authorization boundary re-queries the current administrator role for every
privileged operation and fails closed with one neutral Gradio-visible error.

Settings reads, writes, current-user display, and password changes can no
longer be redirected with forged State. Sign-out resets defaults without a
user DB read. User list/detail/create/save/delete operations authorize before
validation or target access, self-delete compares the request principal, and
unknown targets use the same non-disclosing error. Issue reports record the
request principal and accept a persisted conversation only for its owner or
when it is public; they do not load server conversation history.

## Compatibility and public surface

- `MARA`, `MARA-cli`, launcher authentication, password policy, SSO
  provisioning, DB schemas, Settings JSON keys, and IssueReport JSON shapes
  are unchanged.
- Gradio callback component inputs, outputs, event names, button labels, and
  `.then` order are unchanged. `gr.Request` is injected as a special argument
  and is not a component input.
- Authorized callback method names and return tuple/dataframe shapes are
  unchanged.
- Local/auto mode preserves State/default-user behavior. Password/SSO mode now
  intentionally rejects State-only callback calls.
- The module-level setup/provisioning `create_user(...)` remains outside the
  Web authorization boundary as planned.

## Changed implementation

- `ktem/auth/authorization.py`: request principal resolution, per-operation
  administrator recheck, missing-request sentinel, and typed neutral error.
- `pages/settings.py`: request-scoped load/save/name/password operations and a
  principal-free sign-out default reset; broad-exception upsert control flow
  was removed.
- `pages/resources/user.py`: admin authorization before every User DB callback,
  request-principal self-delete protection, and neutral unknown-target lookup.
- `pages/resources/__init__.py`: request-authorized Users-tab visibility.
- `pages/chat/report.py`: authenticated attribution and owner/public
  conversation predicate without loading stored chat content.
- Focused callback, Settings, UserManagement, issue-report, and event-binding
  regression suites cover the managed/local and varargs injection boundaries.

## Verification

- Initial focused authorization gate: `85 passed`.
- Additional RED cases:
  - unknown user target exposed SQLAlchemy `NoResultFound`;
  - report binding assertion identified the exact keyword component port;
  - callback authorization error was not a Gradio-visible error.
- Final focused Task 12G gate: `26 passed, 2 warnings`.
- Final full ktem gate: `1196 passed, 45 warnings in 34.26s`.
- Full `scripts/check_codebase_hygiene.py`: green; baseline unchanged.
- All changed-file pre-commit hooks: green, including Black, isort, flake8,
  mypy, secret checks, and codespell.
- `git diff --check`: green; worktree clean at report preparation.
- Static selector review confirmed every named Web User/Settings/Conversation
  selector is preceded by request-principal or admin authorization. The only
  intentionally principal-free User selectors are the module-level setup
  provisioning primitive.

## Storage and quota

- Tests used
  `/mnt/fastscratch/users/tbczhang/mara_runtime/quality-hardening-tests` as
  `KH_APP_DATA_DIR`; no live runtime DB was selected.
- Repository `.venv` remained a symlink to the fastscratch environment and no
  repo-root `data/`, `datasets/`, or `outputs/` directory was introduced.
- The latest session preflight still records scratch inode grace pressure and
  fastscratch below its soft file quota; this task performed no install or
  download.

## Baseline debt and residual risk

- `scripts/codebase_hygiene_baseline.json` was not changed or raised. No new
  production module/class/function exceeds the 600/300/80 budgets.
- Last-admin protection, demotion policy, administrator audit logging, account
  recovery, and password history remain explicitly deferred.
- Authorization for non-User Resources pages (Index, LLM, Embedding,
  Reranking, MCP) remains outside this slice.
- Issue reports intentionally remain submitted evidence rather than trusted
  server-side chat snapshots.
- Existing Gradio, FastAPI, pypdf, SWIG, and BeautifulSoup deprecation
  warnings remain non-blocking.

Task 12G verdict: **COMPLETE**.
