# Task 12F Completion Report

Date: 2026-07-12

Status: complete

Commit range: `840df56..f55170e`

## Outcome

Every Notebook DB operation now requires an explicit keyword-only `user_id`.
The centralized loader applies authorization in the SQL predicate before
Notebook JSON is returned: writes are owner-only; reads are owner-only by
default and include public conversations only when the caller explicitly sets
`allow_public=True`. Missing and unauthorized IDs raise the same neutral
`NotebookAccessError`.

Gradio Studio roots resolve the request principal once and pass a plain user ID
through note, artifact, generation, regeneration, failure, export, and render
paths. Password/SSO request identity overrides the runtime fallback. Bound UI
callbacks translate the typed access error to the same neutral `gr.Error`.

## Compatibility

- `MARA`, `MARA-cli`, DocQA JSON, Conversation schema, Notebook JSON keys,
  timestamps, IDs, and authorized rendering markup are unchanged.
- Internal Notebook DB signatures intentionally gained required keyword-only
  `user_id`; `get_notebook` also gained explicit `allow_public=False`.
- Pure normalization, rendering, and already-authorized note materialization
  remain principal-free.
- Note, delete, export, generation, regeneration, and conversation-change
  component input/output lists and event order are unchanged. `gr.Request` is a
  special injected argument and is absent from component ports.
- Local/auto mode uses the DocQA runtime user; password/SSO mode requires the
  server request principal.

## Implementation boundaries

- `_runtime_notebook.py`: typed access error, centralized owner/public loader,
  explicit DB entry signatures.
- `_runtime_notebook_guides.py` and
  `_runtime_notebook_materialization.py`: pure responsibilities extracted to
  keep the authorization module within the 600-line budget.
- `studio_callback_identity.py`: named page binding and request-principal
  adapter with neutral UI error mapping.
- Runtime and Studio modules propagate the resolved principal through captured
  artifacts, notebook-note reads, mindmap/failed saves, panels, delete/export,
  and note conversion.
- Note conversion authorizes before materialization or indexing; export
  authorizes before creating an output path.

## Verification

- Service RED: `17 failed`; old APIs accepted no principal and exposed no typed
  access error.
- UI RED: `2 failed, 2 passed`; denial was not yet mapped to neutral Gradio
  error.
- Focused Notebook/Studio/Runtime gate: `88 passed`.
- Full ktem gate: `1172 passed, 44 warnings in 33.04s`.
- Full codebase hygiene: green; baseline unchanged.
- All changed-file pre-commit hooks: green, including Black, isort, flake8,
  mypy, secret checks, and codespell.
- Static query review finds no Notebook `Conversation.id == conversation_id`
  query outside the centralized loader. Remaining matches are session service
  or acceptance code explicitly outside Task 12F.
- New/affected module sizes: `_runtime_notebook.py` 584 lines, guides 60,
  materialization 83, callback identity 37; all new functions remain within
  budget and `DocQARuntime` no longer grew.

## Residual risk

- Task 12C2's owner-scoped `load_session` remains the prerequisite and was not
  reworked here.
- Public conversation Notebook reads intentionally expose Notebook content to
  explicit public-read renderers; public writes remain forbidden.
- Pure `materialize_note_source` cannot authorize by itself. All in-repo UI
  calls now authorize first; future callers must preserve that sequencing.
- Existing framework deprecation warnings remain non-blocking.

Task 12F verdict: **COMPLETE**.
