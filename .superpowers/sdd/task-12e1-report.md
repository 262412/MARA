# Task 12E1 Artifact Production and Single-File Download Report

## 1. Status and commits

Task 12E1 is implemented as three independent tests-first/production/verification
commits on base
`e9f12e7297ce508b0b90ea35f7029799bf7007eb`:

- `bd21d19 test: specify file export artifact isolation`
- `9f1971a security: isolate file export artifacts by source id`
- `35fff42 style: satisfy artifact isolation verification hooks`

This slice covers artifact production/publication and single-file ZIP/simple-HTML
consumption only. It does not change shared physical-source deletion or `Source.path`
reference counting; those remain blocking Task 12E2 work. It also does not include
C2 preview/KG, notebook, admin, browser/CSP, Settings, CLI, or public bulk-download
changes.

## 2. RED to GREEN evidence

The RED commit added the nine cases required by the Task 12E brief in
`test_file_export_isolation.py`. The symlink/duplicate case is parameterized, so the
file executes ten pytest cases. After correcting the test helper to read Gradio
4.39's FileData-shaped `DownloadButton.value`, the old implementation produced:

```text
10 failed, 2 warnings in 7.34s
```

The failures were caused by the intended defects: filename-stem/global directory
matching, shared producer destinations, absent manifest validation/publication,
legacy fallback, and shared ZIP/HTML server outputs. After production changes, the
same file produced:

```text
10 passed, 2 warnings in 6.01s
```

The final broader focused gate covered FileIndex event/identity/selection/element
behavior plus kotaemon readers, multimodal loading, parse cache, and vector indexing:

```text
61 passed, 1 skipped, 4 warnings in 5.93s
```

## 3. Artifact and manifest layout

The database `file_id` is now the sole artifact namespace token. The original
filename remains only in human-readable filenames inside that namespace:

```text
KH_CHUNKS_OUTPUT_DIR/<file_id>/<original-stem>_<chunk-index>.md
KH_MARKDOWN_OUTPUT_DIR/<file_id>/<original-stem>.md
KH_ZIP_OUTPUT_DIR/manifests/v1/<file_id>/manifest.json
KH_ZIP_OUTPUT_DIR/downloads/<file_id>/<request-uuid>/download-<request-uuid>.zip
KH_ZIP_OUTPUT_DIR/downloads/<file_id>/<request-uuid>/download-<request-uuid>.html
```

`kotaemon.artifact_namespace` is the single internal owner of namespace derivation,
producer output paths, manifest publication/read, archive member names, and isolated
download paths. It lives in kotaemon rather than the brief's preferred ktem location
so kotaemon producers do not gain a reverse dependency on the ktem application/UI
package.

The version-1 manifest contains exactly:

```json
{
  "version": 1,
  "file_id": "<file_id>",
  "entries": [
    { "kind": "chunks", "relative_path": "<file_id>/<name>" },
    { "kind": "markdown", "relative_path": "<file_id>/<name>" }
  ]
}
```

Entries are deterministically ordered by kind and path. `IndexPipeline.stream`
publishes through `finish_and_publish_artifacts` only after `handle_docs` and the
existing `finish` operation succeed. Publication writes a unique same-directory
temporary file, flushes and `fsync`s it, then atomically replaces the exact manifest.
A failed `finish` does not publish a manifest.

## 4. Download security boundary

`download_single_file` now performs these operations in order:

1. Resolve the server request principal through the existing identity adapter.
2. Require an owner-scoped `Source.id`/`Source.user` lookup through
   `FileSelectionService.source_name`.
3. Read only the exact versioned manifest for the authorized `file_id`.
4. Validate all entries before creating or exposing an archive.
5. Write the ZIP below a unique file-id/request UUID destination.

Manifest records fail closed when their schema/version/file ID is wrong, an entry is
absolute or contains `.`/`..`/backslashes, the first path component is not the exact
file-id namespace, a component is a symlink, the target is not a regular file, the
resolved target escapes its configured root/namespace, or two entries produce the
same archive name. Missing/invalid manifests and unauthorized probes use the same
non-disclosing reindex-required Gradio error.

The deleted `_download_outputs_for(file_stem)` global scan has no compatibility
replacement. Legacy shared-root artifacts are untrusted cache and require reindexing.
ZIP members intentionally use `chunks/...` and `markdown/...` prefixes so equal
basenames cannot replace each other. A repository documentation search found no
documented legacy archive-member layout requiring a separate user guide/release-note
edit; this report records the intentional surface change.

`download_single_file_simple` also authorizes the file server-side before writing and
uses the same file-id/request isolation. Its positional inputs and two-output toggle
shape remain unchanged.

## 5. Public surfaces and changed files

Unchanged public surfaces:

- `MARA` / `MARA-cli` commands, options, and dispatch
- FileIndex method names and upload/index return values
- `Source` / `Index` DB schemas and persisted row shape
- `download_single_file` and `download_single_file_simple` positional component inputs
- `(is_zipped_state, gr.DownloadButton)` return shape
- `DOWNLOAD_MESSAGE`, button labels, click-toggle behavior, SSO branch, and Gradio event
  ordering
- public `download_all_files`

The seven implementation/test files are:

- `libs/kotaemon/kotaemon/artifact_namespace.py`
- `libs/kotaemon/kotaemon/indices/vectorindex.py`
- `libs/kotaemon/kotaemon/loaders/html_loader.py`
- `libs/kotaemon/kotaemon/loaders/azureai_document_intelligence_loader.py`
- `libs/ktem/ktem/index/file/pipelines.py`
- `libs/ktem/ktem/index/file/_scoped_page.py`
- `libs/ktem/ktem_tests/test_file_export_isolation.py`

`_download_events.py` was characterized but not modified, preserving component inputs,
two outputs, labels, branches, and event order.

## 6. Hygiene and verification

Final commands and results:

- focused ktem+kotaemon pytest gate: `61 passed, 1 skipped`, exit 0
- security regression file: `10 passed`, exit 0
- `scripts/check_codebase_hygiene.py <changed-files>`:
  `No codebase hygiene ratchet violations.`, exit 0
- `python -m pre_commit run --files <changed-files>`: all hooks passed, including
  hygiene, Black, isort, flake8, autoflake, mypy, and codespell
- base-to-HEAD `git diff --check`: exit 0
- negative single-download scan gate: no `_download_outputs_for`, `os.listdir`, stem,
  prefix, or substring scan; exit 0
- negative producer scan gate: no direct filename-stem write to a shared configured
  chunks/markdown root; exit 0

No hygiene baseline was refreshed or increased. The first hygiene run correctly
rejected growth in existing baseline files (`vectorindex.py`, Azure loader, and
`pipelines.py`). Writer/rendering logic and runtime manifest configuration were moved
to the focused module instead. The final `pipelines.py` remains exactly its existing
990-line baseline, `vectorindex.py` shrank below its baseline, and the new 357-line
module and all new functions remain within the 600/80 budgets. The 359-line security
test is a readable multi-case fixture and remains below the module budget.

Non-final errors and remediation:

- initial GREEN was `6 passed, 4 failed`; all four paths were already correctly
  fail-closed, but the generic message used uppercase `Reindex` while the security
  contract asserted lowercase `reindex`; production copy was normalized
- initial hygiene failed on baseline growth; responsibilities were extracted without
  updating the baseline or compressing fixtures
- first production pre-commit found an unused `Path` import after extraction;
  autoflake removed it and the fresh run passed every hook

Warnings are dependency deprecations from BeautifulSoup/lxml, pypdf cryptography
ARC4, and do not originate in this slice.

## 7. Storage and residual risk

Final storage preflight evidence:

- repo: `/mnt/scratch/users/tbczhang/projects/MARA-quality-hardening`
- `.venv`: symlink to `/mnt/fastscratch/users/tbczhang/envs/mara`
- Python: fastscratch CPython 3.10.20
- cache/runtime variables: fastscratch; pre-commit cache: scratch
- repo root: no `data/`, `datasets/`, or `outputs/`
- fastscratch: `295.8G`, `471891 / 500000` soft inode quota
- scratch: `71.91G`, `473128 / 300000` soft and `500000` hard inode quota; still in
  grace

Tests used the configured temporary pytest runtime. No dependency install, model call,
dataset sync, indexing of user data, or large download occurred.

Residual/blocking work:

- Task 12E2 must implement the shared `Source.path` lifetime lock/refcount/quarantine
  sequence and file-id artifact deletion. E1 does not make physical blob deletion safe
  and does not claim the full Task 12E shared-source invariant.
- Legacy global artifacts remain on disk until reindex/manual follow-up, but are never
  consumed by the single-file download path.
- A failed producer/index run can leave an unmanifested file-id namespace; it is not
  downloadable. Cleanup belongs with E2 deletion or a later orphan-GC audit.
- The focused gate did not run browser/live Gradio, model, LibreOffice, or full
  repository suites; event ABI/order is protected by existing browser-free contracts.
- Both scratch and fastscratch inode pressure remain operational risks for future large
  runs.

Task 12E1 verdict: **DONE**, with Task 12E2 explicitly still blocking completion of the
full Task 12E brief.
