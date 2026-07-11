# Task 12G: Settings, User Administration, and Feedback Identity

This slice closes identity-audit F-06 and the lower-severity F-05 attribution
gap. It introduces one shared Web authorization helper, then applies it to
Settings, UserManagement, Resources visibility, and issue reporting. Implement
tests first. UI visibility remains defense in depth; every DB operation must
authorize independently.

## Authorization contract

- In `password` and `sso` modes, the only request principal is
  `ktem.auth.service.resolve_request_user_id(gr.Request, auth_mode=...)`.
  Browser/Gradio State user IDs are never authority.
- In `local` and `auto` modes, preserve the existing local/default State user
  behavior. Do not require a managed-login request where the product currently
  runs without one.
- Settings load/save/name/password callbacks resolve the server principal
  before selecting a `User` or `Settings` row. Forged State must not redirect a
  read, write, or password change.
- UserManagement list/detail/create/save/delete callbacks call `require_admin`
  before validation, target lookup, or mutation. `require_admin` resolves the
  request user and re-queries `User.admin` server-side on every operation.
  Hidden tabs/buttons are not authorization.
- Admin self-delete protection compares the selected target with the resolved
  server principal, not the State current user.
- Issue reports record the resolved request principal. A non-empty
  `conversation_id` is accepted only when that principal owns the conversation
  or the conversation is explicitly public. Empty conversation IDs remain
  valid for feedback without a persisted chat. The report callback never loads
  another conversation's history; callback-provided history/settings remain
  submitted evidence, not trusted server content.
- Missing principal, non-admin, unknown target, and unauthorized conversation
  fail before side effects with neutral/non-disclosing UI errors.

Add one focused internal module, preferably
`libs/ktem/ktem/auth/authorization.py`, with two narrow boundaries:

- `resolve_callback_user_id(state_user_id, request)`: managed modes require the
  request principal; local/auto returns the existing State/default user.
- `require_admin(state_user_id, request)`: resolves the callback user, queries
  the current `User` row, and returns its ID only when `admin is True`.

Keep policy here and presentation in page modules. Do not copy auth-mode
branches into each callback. Use the existing missing-request sentinel pattern
for direct local calls, but password/SSO calls without an injected request must
fail closed.

## Exact affected surfaces

### Shared authorization

- `libs/ktem/ktem/auth/service.py`
  - reuse `resolve_request_user_id`; do not change password verification, SSO
    provisioning, or the launcher auth contract.
- New `libs/ktem/ktem/auth/authorization.py`
  - normalize auth mode, resolve callback user, require admin, and expose one
    typed authorization error that page roots map to a neutral `gr.Error`.
  - authorization tests inject the DB engine; do not introduce module-level
    cached User/admin state.

### Settings principal

- `libs/ktem/ktem/pages/settings.py`
  - `on_subscribe_public_events`: `load_setting` and current-user name lookup
    receive exact injected `gr.Request`; keep event names and outputs.
  - `on_register_events`: `save_setting` and `change_password` receive exact
    request without adding a component input.
  - `change_password`: resolve first, then select/update only that `User`.
  - `load_setting`: select only the resolved user's `Settings` row.
  - `save_setting`: upsert only the resolved user's row; State is a local-mode
    fallback, not a managed-mode selector.
  - split the sign-out reset into a principal-free defaults-only callback so it
    cannot accidentally reload the still-authenticated request user's DB row.
  - preserve `get_name` display behavior while resolving its DB lookup from the
    request principal.

`save_setting` currently has `*args`; place an exact `request: gr.Request`
positional parameter before the varargs so Gradio 4.39 can discover and inject
it. Request must not be appended after `*args` or added to `inputs=[...]`.

### UserManagement admin boundary

- `libs/ktem/ktem/pages/resources/user.py`
  - `UserManagement.create_user`: require admin before username/password checks
    or duplicate lookup.
  - `UserManagement.list_users`: require admin before listing any User row.
  - `UserManagement.on_selected_user_change`: require admin before target
    detail lookup.
  - `UserManagement.save_user`: require admin before validation, uniqueness
    query, password hash, role change, or commit.
  - `UserManagement.delete_user`: require admin, compare target with the
    resolved admin ID, then delete.
  - preserve `select_user` and delete-confirm UI helpers as pure presentation;
    they do not replace authorization at the DB callbacks.
  - keep module-level `create_user(usn, pwd, user_id=None, is_admin=True)` as an
    explicit non-Web provisioning primitive used by setup/CLI. Do not route the
    Web callback around `require_admin` through that helper.
- `libs/ktem/ktem/pages/resources/__init__.py`
  - `ResourcesTab.toggle_user_management` uses the resolved request principal
    for accurate visibility. The downstream UserManagement checks remain the
    security boundary even when the tab is visible.

All `.click`, `.change`, `.then`, and public-event bindings retain their current
component inputs and output order. Add exact `gr.Request` annotations to the
callback functions; Gradio injects them as special arguments.

### Issue-report attribution

- `libs/ktem/ktem/pages/chat/report.py`
  - `ReportIssue.report`: resolve request identity before building selector
    metadata or opening an IssueReport write session; set `IssueReport.user` to
    that principal.
  - for non-empty `conv_id`, authorize with a predicate on
    `Conversation.id` and `(Conversation.user == principal) |
    Conversation.is_public`; do not fetch server chat history.
  - place exact `request: gr.Request` before `*selecteds` so Gradio 4.39 scans
    it. Keep dynamic index selections in their existing order.
- `libs/ktem/ktem/pages/chat/chat_auxiliary_events.py`
  - characterize `_bind_user_feedback_events`; keep the existing report
    component inputs and `outputs=None`. `gr.Request` is not a component.

## RED cases to land first

Add `libs/ktem/ktem_tests/test_settings_server_identity.py`:

- `test_managed_settings_load_uses_request_principal_not_state_user`
- `test_managed_settings_save_cannot_write_forged_state_user`
- `test_password_change_updates_only_request_principal`
- `test_missing_managed_request_identity_performs_no_settings_or_user_write`
- `test_local_mode_retains_state_default_settings_behavior`
- `test_signout_reset_reads_defaults_without_user_db_lookup`
- `test_settings_request_is_injected_without_component_abi_change`

Use different settings and password hashes for victim and attacker. Assert the
entire victim row/hash remains unchanged after denial or forged State.

Add `libs/ktem/ktem_tests/test_user_management_authorization.py`:

- `test_non_admin_direct_callback_cannot_create_user`
- `test_non_admin_cannot_list_or_read_selected_user`
- `test_non_admin_cannot_save_user_or_change_admin_role`
- `test_non_admin_cannot_delete_user`
- `test_forged_admin_state_loses_to_non_admin_request`
- `test_admin_can_create_list_read_save_and_delete_other_user`
- `test_admin_self_delete_uses_request_principal_and_is_denied`
- `test_hidden_tab_fn_index_call_still_requires_admin`
- `test_user_management_request_is_special_not_component_input`
- `test_local_mode_admin_lookup_uses_existing_state_user`

For every denial, assert no duplicate lookup/target query or commit occurs after
the admin check. Keep authorized return tuples/dataframe columns as golden
characterization assertions.

Add `libs/ktem/ktem_tests/test_issue_report_server_identity.py`:

- `test_issue_report_records_request_principal_not_state_user`
- `test_issue_report_rejects_private_non_owner_conversation`
- `test_issue_report_allows_owner_public_and_empty_conversation_ids`
- `test_denied_issue_report_writes_no_row_and_reads_no_chat_history`
- `test_issue_report_request_injection_preserves_dynamic_index_inputs`

Use a forged victim State ID and private conversation marker. Assert the marker
is never fetched from `Conversation.data_source`; only the submitted callback
payload may appear in the new IssueReport.

Extend existing binding/auth tests where they already own the contract:

- `test_chat_conversation_event_security.py` keeps report input ordering.
- `test_auth_service.py`, `test_auth_policy.py`, and `test_auth_managed_user.py`
  cover managed/local resolution and existing password/SSO behavior.

## Compatibility constraints

- Preserve `MARA` / `MARA-cli`, launcher login/logout, password hash/validation
  policy, SSO user provisioning, and all User/Settings/IssueReport DB schemas.
- Preserve authorized callback method names, component input/output counts,
  return tuple/dataframe shapes, button labels, event names, and `.then` order.
  `gr.Request` is injected and never appears in component input lists.
- Preserve Settings JSON keys/default merge behavior and current save/change
  success messages for authorized users.
- Preserve UserManagement username/password validation, uniqueness behavior,
  default non-admin Web-created users, and current self-delete prohibition.
- Preserve local/auto single-user behavior. Password/SSO modes intentionally
  stop accepting State-only direct calls.
- Preserve issue payload/chat/settings JSON shape. The intentional change is
  server-authenticated `IssueReport.user` plus validation of a non-empty
  conversation label.
- Unknown/unauthorized IDs use neutral errors and do not disclose whether the
  target user or private conversation exists.

## Explicitly out of scope

- Download artifacts/shared physical Source lifetime (Task 12E).
- Notebook/runtime conversation authorization (Task 12F) and Task 12C2
  preview/KG/session work.
- Changing `authenticate_password`, OIDC claims, cookies, session-hash storage,
  launcher routes, or adding a new role/permission model.
- Removing or request-authorizing the module-level provisioning
  `create_user(...)`; it is not a Web callback.
- Last-admin/demotion policy, admin audit logs, soft deletion, account recovery,
  password reset, or password-history features.
- Treating issue reports as trusted chat snapshots, reloading conversation
  history into reports, moderation, retention, or report-admin UI.
- Broad Resources permissions for Index/LLM/Embedding/Reranking/MCP pages; this
  slice covers only the existing Users tab and named callbacks.

## Exit gates

The slice is complete only when all of the following hold:

1. New tests are observed RED on current behavior and GREEN after the minimal
   changes; each denial proves zero DB/file side effects.
2. `rg` finds no Settings/UserManagement/issue-report DB selector whose user or
   admin authority comes only from Gradio State, and no admin operation guarded
   only by tab/button visibility.
3. Exact Gradio 4.39 injection tests cover normal methods plus the
   `save_setting` and `ReportIssue.report` varargs boundaries without changing
   component inputs.
4. Focused settings, resources/user, report, auth-policy, managed-user, and chat
   binding tests pass, followed by the relevant `libs/ktem` package gate.
5. `scripts/check_codebase_hygiene.py <changed-files>` passes with no baseline
   refresh/increase; new module/class/function sizes stay within 600/300/80.
6. Relevant pre-commit hooks and `git diff --check` pass after the mandatory
   storage preflight, using temporary runtime roots.
7. Handoff lists affected public surfaces, managed/local behavior, internal
   helper/API changes, exact commands/results, baseline debt, and residual risk
   (especially the explicitly deferred last-admin and broader Resources policy).
