# Task 12F: Notebook and Runtime Conversation Authorization

This slice closes the notebook half of identity-audit F-03. It starts after
Task 12C2 request-principal plumbing is available and reuses that resolver. It
does **not** implement or revisit C2's
`DocQARuntime.load_session(..., user_id=resolved_user_id)` prerequisite.
Implement the service boundary tests first, then propagate the principal to
each existing caller without changing component ports.

## Authorization contract

- Every `_runtime_notebook` function that reaches `Conversation` requires an
  explicit normalized `user_id`. The runtime's construction-time/default user
  is not an authorization argument for a Web request.
- Read APIs use one explicit policy: the owner may read; a non-owner may read
  only when `Conversation.is_public is True` and that caller opts into public
  read. Default is private/owner-only.
- Every mutation is owner-only, including artifact save/delete, failed-artifact
  save, export recording, note save, selected-source updates, note-to-source
  recording, generation, and regeneration. Public conversations are not
  publicly writable.
- Missing and unauthorized conversation IDs produce the same non-disclosing
  typed `NotebookAccessError` (mapped to the existing neutral Gradio failure at
  UI roots). Do not reveal whether a victim conversation exists.
- Authorization happens in the SQL predicate before notebook JSON is returned
  and before any filesystem write, note materialization, indexing call, model
  call, or DB mutation.
- Pure notebook normalization/render helpers that accept an already-authorized
  dict remain principal-free. Do not turn data transforms into DB services.

Use one owner-aware loader in `ktem.docqa._runtime_notebook`, for example
`_load_conversation(session, conversation_id, user_id, access)`. A read query
may include `(Conversation.user == user_id) | Conversation.is_public`; a write
query includes only `Conversation.user == user_id`. Public-read opt-in must be
visible at the caller, not inferred from a generic truthy flag or UI state.

## Exact affected surfaces

### Notebook DB boundary

- `libs/ktem/ktem/docqa/_runtime_notebook.py`
  - `save_artifact_to_conversation`
  - `delete_artifact_from_conversation`
  - `record_artifact_export_to_conversation`
  - `save_captured_artifact`
  - `_load_conversation`
  - `get_notebook`
  - `add_note_to_conversation`
  - `save_answer_note_to_conversation`
  - `select_conversation_sources`
  - `record_note_indexed_source_to_conversation`
  - add the typed access error and make `user_id` keyword-only on every DB
    entry. Preserve notebook normalization, IDs, timestamps, and JSON keys.

### Runtime persistence

- `libs/ktem/ktem/docqa/runtime.py`
  - `_finalize_turn_response` already has `resolved_user_id`; pass it to
    `_save_turn_artifact` and then `save_captured_artifact`.
  - notebook note reads used by Studio generation must receive the same
    resolved user that the turn uses.
  - do not change `load_session` in this slice; that exact session-read change
    belongs to Task 12C2.
- `libs/ktem/ktem/pages/chat/studio_artifact_generation.py`
  - `_notebook_note_records` and generation/regeneration paths must consume the
    principal already resolved at the C2 root callback.
- `libs/ktem/ktem/pages/chat/studio_artifact_mindmap.py`
  - pass the resolved principal only to the notebook artifact save. Source/KG
    authorization remains Task 12C2.
- `libs/ktem/ktem/pages/chat/studio_artifact_status.py`
  - `save_failed_studio_artifact`, `_latest_notebook_artifact`, and failure
    panel rendering receive the resolved principal; a failed generation must
    not become an ownerless write.

### Gradio notebook roots and renderers

- `libs/ktem/ktem/pages/chat/studio_note_controls.py`
  - save-answer, save-artifact, save-manual-note, and convert-note bindings keep
    their current component inputs/one output. Exact `gr.Request` is a special
    callback argument, never a component.
- `libs/ktem/ktem/pages/chat/studio_note_actions.py`
  - all four update functions resolve/reuse the server principal and pass it to
    notebook reads/mutations. `convert_note_to_source_update` must authorize
    before creating a note file or invoking DocQA indexing.
- `libs/ktem/ktem/pages/chat/studio_artifact_controls.py`
  - delete/export/regenerate bindings keep current inputs and outputs.
  - C2 owns the exact-Request/varargs repair on generate/regenerate roots;
    12F only consumes C2's resolved user for notebook operations.
- `libs/ktem/ktem/pages/chat/studio_artifacts.py`
  - `render_conversation_notebook_panel_html` and
    `render_conversation_notebook_update` are explicit public-read callers.
  - `delete_latest_artifact_update` and `export_latest_artifact_update` are
    owner-only. Authorize before computing/writing the export path and before
    recording the export.
- `libs/ktem/ktem/pages/chat/studio_artifact_results.py`
  - `_conversation_artifacts` and
    `render_conversation_studio_results_html` use explicit public-read policy;
    no marker from a private victim may reach rendered HTML.
- `libs/ktem/ktem/pages/chat/studio_artifact_outputs.py`
  - `generation_panel_outputs` and `latest_notebook_artifact` propagate the
    already-resolved owner principal. Generation output is not a public-read
    path because it can follow a mutation.
- `libs/ktem/ktem/pages/chat/__init__.py`
  - the conversation-change notebook render binding retains its current input,
    output, and chain position while receiving exact injected `gr.Request`.

Avoid passing `gr.Request` through render/data helpers. Resolve it once at each
Gradio root, then pass a plain `user_id` through internal calls. Direct-call
tests may use the repository's existing missing-request sentinel only in
local/auto mode; password/SSO mode must fail when no request principal exists.

## RED cases to land first

Add `libs/ktem/ktem_tests/test_docqa_notebook_authorization.py`:

- `test_owner_can_read_and_mutate_notebook`
- `test_private_notebook_read_hides_missing_and_non_owner_equally`
- `test_each_notebook_mutation_rejects_non_owner_without_json_change`
- `test_public_notebook_read_requires_explicit_opt_in`
- `test_public_notebook_mutations_remain_owner_only`
- `test_export_record_requires_owner`
- `test_selected_sources_and_indexed_note_records_require_owner`
- `test_runtime_turn_passes_resolved_user_to_captured_artifact_save`

Parameterize the mutation test over all DB-writing entry points. Compare the
entire `Conversation.data_source` before/after denial and use unique private
markers in notes, artifacts, prompts, and export metadata.

Extend focused UI/runtime tests:

- `test_studio_artifacts.py`
  - private victim panel/results render never contains its marker;
  - public render succeeds read-only;
  - non-owner delete/export creates no file and changes no JSON;
  - owner export keeps the configured path/format and panel return shape.
- `test_studio_note_actions.py` and `test_studio_note_workflow.py`
  - forged browser/session owner loses to request principal;
  - denied save/convert performs no temp-file or index call;
  - owner behavior and returned panel HTML remain unchanged.
- `test_studio_artifact_generation.py`
  - generation, regeneration, mindmap save, and failed-artifact save pass the
    resolved owner; a public non-owner cannot append artifacts.
- `test_studio_chat_page_bindings.py`
  - Gradio 4.39 injects exact `gr.Request`; it is absent from component inputs;
  - delete 1-to-1, export 2-to-1, note bindings, generation 12 outputs, and all
    `.then` ordering remain unchanged.
- `test_docqa_runtime.py` / `test_docqa_runtime_streaming.py`
  - capture save receives the resolved turn user, not the shared runtime
    default.

Tests must assert denial occurs before spies for export write, materialization,
indexing, or model execution. Do not rely only on a final DB assertion.

## Compatibility constraints

- Preserve `MARA` / `MARA-cli`, DocQA request/response JSON, Conversation DB
  schema, and the existing notebook JSON schema and rendering markup for an
  authorized caller.
- Internal notebook DB function signatures intentionally become explicit and
  keyword-only for `user_id`; update every in-repo caller in the same slice.
  Principal-free pure transforms retain their signatures.
- Preserve public-conversation read behavior already established by
  `RuntimeSessionService`; only writes become uniformly owner-only.
- Preserve all Gradio component input/output counts, ordering, direct-call
  return shapes, button labels, and event chain order. Injected `gr.Request`
  must not appear in `inputs=[...]`.
- In `local`/`auto` auth mode, retain the existing default/local user behavior.
  In `password`/`sso`, missing server identity fails closed even if State
  contains a user ID.
- Keep neutral empty/error rendering for unknown and unauthorized IDs. Do not
  introduce different messages, status text, or timing-dependent branches that
  disclose existence.

## Explicitly out of scope

- Task 12C2's `DocQARuntime.load_session(..., user_id=resolved_user_id)` change,
  preview resolver, source selectors, KG/docstore, mindmap source ownership,
  page scope, and timer/navigation authorization.
- Download artifact namespace and physical Source refcount (Task 12E).
- Settings, UserManagement/admin, and issue-report identity (Task 12G).
- Changing public/private conversation semantics outside notebook reads.
- New collaboration/sharing roles, ACL tables, per-note ownership, or notebook
  schema migration.
- Changing Studio artifact formats, generation prompts/models, note-indexing
  content, export media adapters, or export retention policy.
- Browser/CSP changes and broad Gradio event refactors.

## Exit gates

The slice is complete only when all of the following hold:

1. Every new authorization test is observed RED against the pre-change service
   or callback, then GREEN after the minimal implementation.
2. `rg` finds no `Conversation.id == conversation_id` notebook query outside
   the centralized owner-aware loader and no DB notebook entry callable without
   explicit `user_id`.
3. Focused notebook, Studio artifact/note/workflow, binding, DocQA runtime, and
   public-conversation tests pass, followed by the relevant `libs/ktem` package
   gate.
4. Exact Gradio request-injection tests prove server principal wins over State,
   and all side-effect-before-authorization spies remain untouched on denial.
5. `scripts/check_codebase_hygiene.py <changed-files>` passes with no baseline
   refresh/increase; new module/class/function sizes stay within 600/300/80.
6. Relevant pre-commit hooks and `git diff --check` pass using temporary runtime
   roots after the mandatory storage preflight.
7. Handoff lists internal signature changes, public-read policy, preserved UI
   ABI, exact commands/results, baseline debt, and residual risk. It explicitly
   states that C2 session-load authorization was a prerequisite, not reworked
   here.
