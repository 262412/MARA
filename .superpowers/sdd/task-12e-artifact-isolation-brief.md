# Task 12E: File Artifact Namespace and Shared-Source Lifetime

This is the smallest rollback-safe slice that closes identity-audit F-01 and
the related shared physical-source deletion defect. It must be implemented
tests first. It is independent of Task 12C2 and must not absorb preview, KG,
notebook, Settings, or admin authorization work.

## Security contract

1. A private file's exported chunks and markdown are identified by its
   database-issued `file_id`, never by the user-visible filename or stem.
2. A single-file download first authorizes `(Source.id, Source.user)` and then
   consumes only an exact manifest for that authorized `file_id`. A global
   directory scan, substring match, prefix match, or same-stem fallback is not
   an authorization mechanism.
3. Manifest entries are relative, regular, non-symlink files under the exact
   configured root and the exact `file_id` namespace. Absolute paths, `..`,
   root escape, cross-namespace entries, and duplicate archive names fail
   closed before any archive is exposed.
4. ZIP and simple-HTML outputs have a per-file plus per-request destination;
   two users or concurrent requests with the same original stem cannot
   overwrite or observe one another's output.
5. A content-addressed physical source is unlinked only when no committed
   `Source` row references its `Source.path`. The storage path critical section
   must cover both upload publication and deletion/refcount decisions. If a
   concurrent state cannot be proven unreferenced, retain an orphan rather than
   delete a live blob.

Keep the manifest internal and versioned. A minimal version-1 record is
`file_id` plus ordered entries of `{kind: chunks|markdown, relative_path}`.
Publish it atomically only after successful indexing. The namespace token may
be a validated `file_id` path component or a stable digest of `file_id`; it
must not contain the original filename and must map one-to-one to the source.
Put archive members below `chunks/` and `markdown/` so equal basenames cannot
silently replace each other.

## Exact affected surfaces

### Artifact production and publication

- `libs/ktem/ktem/index/file/pipelines.py`
  - `BaseFileIndexIndexing.stream`: `extra_info["file_id"]` is already the
    canonical producer input; finalize and atomically publish the manifest only
    after `handle_docs` and `finish` succeed.
  - `BaseFileIndexIndexing.store_file`: join the shared physical-path lifetime
    critical section used by deletion. Preserve SHA-256 content addressing and
    the existing `Source` row shape.
- `libs/kotaemon/kotaemon/indices/vectorindex.py`
  - `VectorIndexing.write_chunk_to_file`: select the output namespace from
    document metadata `file_id`; retain human-readable chunk filenames only
    inside that namespace.
- `libs/kotaemon/kotaemon/loaders/html_loader.py`
  - `MhtmlReader.load_data`: write generated markdown below the `file_id`
    namespace obtained from `extra_info`.
- `libs/kotaemon/kotaemon/loaders/azureai_document_intelligence_loader.py`
  - the markdown cache write in `load_data`: use the same namespace contract.
- Add one focused internal module, preferably
  `libs/ktem/ktem/index/file/artifact_namespace.py`, for namespace derivation,
  atomic manifest publication/read, containment validation, archive member
  names, and per-request output paths. Do not spread path rules across loaders
  and UI callbacks.

### Download consumption

- `libs/ktem/ktem/index/file/_scoped_page.py`
  - `download_single_file`: retain request-principal resolution and the
    owner-scoped Source lookup, keep the `file_id`, read its exact manifest,
    validate every entry, and create an isolated ZIP.
  - `download_single_file_simple`: create an isolated HTML output keyed by the
    authorized `file_id` and request token rather than `<stem>.html`.
  - remove `_download_outputs_for(file_stem)`; there must be no legacy global
    scan. A missing/invalid manifest yields the same non-disclosing,
    reindex-required download failure for owner and non-owner probes.
- `libs/ktem/ktem/index/file/_download_events.py`
  - characterize only; component inputs, two outputs, labels, toggle state, and
    event ordering must remain unchanged.

### Shared physical-source deletion

- `libs/ktem/ktem/index/file/deletion.py`
  - `_DeletionPlan` must retain the stored relative `Source.path`, not only its
    resolved filesystem path.
  - replace unconditional `_delete_stored_file` with a DB-derived
    remaining-reference decision under the same path critical section used by
    `store_file`.
  - keep `(Source.id, Source.user)` validation, store deletion ordering, path
    containment, symlink rejection, and actionable `DeletionError` stages.
  - sequential last-reference deletion removes the blob. Concurrent ambiguity
    may leave a zero-reference orphan, but must never unlink while a committed
    survivor exists.
  - delete only the current `file_id` artifact namespace/manifest; never use
    the shared content hash to select generated artifacts.
- `libs/ktem/ktem/index/file/pipelines.py` and
  `libs/ktem/ktem/index/file/_deletion.py` are the two current coordinator call
  sites; preserve their return/error contracts.

No DB migration or persisted refcount column is needed: `Source.path` rows are
the source of truth. If a small storage-path lock helper is needed, keep it in
the file-index package and use it from both publication and deletion. It must
not rely on a process-local lock alone when multiple workers can share the
storage root.

Use this failure-safe last-reference sequence: delete vector/docstore entries;
acquire the shared-path lock; in one SQL transaction delete the owner-scoped
Index/Source rows, flush, and count remaining `Source.path` references. When the
count reaches zero, atomically move the blob to a quarantine name inside the
storage root, then commit SQL; restore the move if commit fails. After a
successful commit, unlink the quarantine file. Upload holds the same lock from
atomic blob publication through Source commit. A post-commit unlink failure is
a logged, auditable orphan-GC condition, not permission to restore a deleted
row or remove another live path.

## RED cases to land first

Add `libs/ktem/ktem_tests/test_file_export_isolation.py`:

- `test_single_download_excludes_same_stem_other_file_id`
- `test_single_download_does_not_match_stem_substrings`
- `test_chunk_and_markdown_paths_are_unique_per_file_id`
- `test_download_rejects_manifest_entry_outside_file_namespace`
- `test_download_rejects_manifest_symlink_and_duplicate_archive_name`
- `test_missing_manifest_never_falls_back_to_legacy_stem_files`
- `test_same_stem_concurrent_downloads_use_distinct_output_paths`
- `test_simple_html_downloads_do_not_share_same_stem_output`
- `test_failed_indexing_does_not_publish_downloadable_manifest`

Use two owners, two `file_id` values, equal stems, and unmistakable victim
markers. Assert archive member names and bytes, not just returned paths.

Extend `libs/ktem/ktem_tests/test_deletion_coordinator.py`:

- `test_deleting_one_of_two_sources_sharing_path_keeps_physical_blob`
- `test_deleting_last_source_reference_unlinks_physical_blob`
- `test_reference_count_is_global_across_owners`
- `test_concurrent_shared_path_delete_never_breaks_surviving_source`
- `test_upload_delete_interleaving_never_commits_source_to_missing_blob`
- `test_file_id_artifacts_are_removed_without_touching_other_namespace`
- retain the existing owner, retry, traversal, symlink, vector, and docstore
  cases as characterization tests.

The concurrency tests should use barriers/fake sessions or a deterministic
interleaving hook, not timing sleeps. Their hard invariant is safety of every
committed survivor; a conservative orphan is acceptable and should be visible
to a later, separately testable GC pass.

## Compatibility constraints

- Preserve `MARA` / `MARA-cli`, FileIndex method names, Source/Index DB schema,
  upload/index return values, and existing request-principal resolution.
- Preserve `download_single_file` and `download_single_file_simple` positional
  component inputs and their two-value return shape:
  `(is_zipped_state, gr.DownloadButton)`.
- Preserve `DOWNLOAD_MESSAGE`, button labels, click-toggle behavior, and the
  SSO/simple-download branch.
- ZIP contents remain human-readable. The intentional user-visible change is
  deterministic `chunks/` and `markdown/` member prefixes; cover it with a
  contract test and release note if this surface is documented.
- Preserve content hashing and deduplication. Do not duplicate all physical
  sources per user as a shortcut around reference safety.
- Legacy global stem artifacts are untrusted cache, not downloadable data.
  Existing files require reindexing to obtain a manifest; do not add an unsafe
  compatibility fallback.
- Use configured temp/runtime roots in tests. Do not create repository-root
  `data/`, `datasets/`, or `outputs/` directories.

## Explicitly out of scope

- Public-index `download_all_files` behavior.
- F-02 preview, F-03 KG/mindmap, F-04 selector scope, and Task 12C2 work.
- Notebook/runtime conversation authorization (Task 12F).
- Settings, UserManagement, and issue-report identity (Task 12G).
- A bulk migration or deletion of legacy global artifacts.
- A general-purpose object-store abstraction, remote blob-store support, or a
  background GC service. A safe orphan audit/GC can be a follow-up.
- Parse-cache, embedding-cache, docstore, or vector-store layout changes beyond
  the exact generated download artifacts above.

## Exit gates

The slice is complete only when all of the following hold:

1. The RED tests fail on the pre-change implementation for the stated reason,
   then pass after the minimal implementation.
2. `rg` finds no filename-stem scan in the single-file download path and no
   producer write directly to a shared chunks/markdown root.
3. Focused export, producer, deletion, and deletion-call-site tests pass,
   followed by the relevant `libs/ktem` and `libs/kotaemon` package gates.
4. `scripts/check_codebase_hygiene.py <changed-files>` passes with no baseline
   refresh or increase; new module/class/function sizes stay within 600/300/80.
5. Relevant pre-commit hooks pass, `git diff --check` is clean, and a storage
   preflight confirms `.venv` remains the fastscratch symlink and runtime/cache
   writes stayed outside the repo.
6. The handoff records the manifest/cache layout change, legacy reindex need,
   shared-source concurrency invariant, any conservative orphan risk, exact
   commands/results, and all affected public surfaces.
