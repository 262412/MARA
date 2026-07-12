# Task 12E2 Completion Report

Date: 2026-07-12

Status: complete

Commit range: `1eeef55..ef216a7`

## Outcome

Shared content-addressed source files now have one cross-process lifetime
contract for upload and deletion. A deletion cannot unlink a blob while any
committed `Source.path` reference remains, including references owned by a
different user. The last-reference path is quarantined before SQL commit,
restored on commit failure, and purged only after commit. A purge failure is an
auditable orphan condition and does not turn a committed deletion into a false
failure.

Generated chunks, markdown, manifests, and isolated downloads are cleaned by
exact `file_id` namespace. The content hash is never used to select generated
artifacts, so deleting one source cannot remove another source's generated
data merely because both share physical bytes.

## Commits

- `1af0422 test: specify shared source deletion`
- `d444b23 test: specify storage lifetime primitives`
- `5fdb4db security: add shared storage lifetime primitives`
- `196d41c test: specify shared storage interleavings`
- `5304365 security: coordinate shared source deletion`
- `ef216a7 test: refresh secured runtime expectations`

The final commit is test-only maintenance for four package-gate expectations
that had drifted after earlier server-identity and Gradio callback hardening.
No production behavior was changed to satisfy them.

## Changed production surfaces

- `libs/ktem/ktem/index/file/storage_lifetime.py`
  - stable SHA-256 lock names under `.mara-locks`;
  - `filelock`-backed cross-process leases;
  - atomic publish, quarantine, restore, and purge;
  - relative-path, symlink, directory, and root containment rejection;
  - quarantine directory-sync failure restores the original blob.
- `libs/ktem/ktem/index/file/source_storage.py`
  - holds the shared path lease from atomic publication through `Source`
    commit.
- `libs/ktem/ktem/index/file/deletion.py`
  - retains the stored relative `Source.path` in the deletion plan;
  - deletes vector, all docstore relation types, and file-id artifacts before
    relational removal;
  - performs owner-scoped Index/Source deletion, flush, global refcount,
    quarantine, and commit under one path lease;
  - restores the blob on SQL failure and logs post-commit purge orphans.
- `libs/ktem/ktem/index/file/artifact_cleanup.py`
  - validates all exact file-id namespaces before fd-safe recursive cleanup;
  - rejects invalid components, symlinks, and non-directory namespaces.
- `pipelines.py`, `_deletion.py`, and `_runtime_file_service.py`
  - upload, pipeline deletion, Web deletion, and DocQA runtime deletion now use
    the shared services and configured artifact roots.
- `libs/ktem/pyproject.toml` and `uv.lock`
  - declare the already locked `filelock>=3.19.1,<4` direct runtime dependency;
    no dependency version was upgraded.

## Compatibility

- `MARA` and `MARA-cli` command names and options are unchanged.
- Deletion success objects and existing CLI JSON fields are unchanged.
- `Source` and `Index` schemas are unchanged; no migration or persisted
  refcount was added.
- Upload continues to use SHA-256 content addressing and returns the same
  database-issued file ID.
- Web error rendering, authenticated principal resolution, Gradio component
  shapes, and event-chain ordering are unchanged.
- The intentional artifact layout from Task 12E1 remains file-id scoped;
  legacy stem caches still require reindexing and receive no unsafe fallback.

## Test-first evidence

- Existing coordinator RED: `8 failed, 11 passed`; failures covered shared and
  cross-owner survivors, quarantine/purge faults, SQL rollback restore, exact
  artifact cleanup, and artifact-cleanup failure.
- Primitive RED: `13 failed`; both lifetime modules were absent.
- Interleaving RED: `3 failed`; the coordinator rejected the lifetime seam and
  upload committed outside the lease.
- Final focused gate: `40 passed in 7.24s`.
- Deterministic concurrency uses barriers/events, not timing sleeps, for:
  concurrent last-reference deletes, upload-commit-first, and
  delete-commit-first outcomes.

## Package and quality gates

- `python -m pytest -q libs/ktem/ktem_tests`:
  `1150 passed, 44 warnings in 34.78s`.
- `python -m pytest -q libs/kotaemon/tests`:
  `346 passed, 8 skipped, 88 warnings in 81.22s`.
- `python scripts/check_codebase_hygiene.py`:
  `No codebase hygiene ratchet violations.`
- `pre-commit run --from-ref 1eeef55 --to-ref HEAD`:
  all hooks passed, including hygiene, secret checks, Black, isort, flake8,
  mypy, and codespell.
- `uv lock --check`: resolved 403 packages, exit 0.
- `git diff --check`: exit 0.
- The hygiene baseline file is unchanged.

New production sizes remain within budget:

- `storage_lifetime.py`: 251 lines
- `artifact_cleanup.py`: 109 lines
- `source_storage.py`: 43 lines
- `deletion.py`: 345 lines

The already-baselined `pipelines.py` decreased from 990 to 980 lines. No new
module exceeds 600 lines and no baseline allowance was added or raised.

## Storage and quota

- `.venv` remains a symlink to
  `/mnt/fastscratch/users/tbczhang/envs/mara`.
- Repository-root `data/`, `datasets/`, and `outputs/` remain absent.
- Runtime/cache settings remain under fastscratch; pre-commit cache remains
  under scratch.
- Final fastscratch usage: 295.8 GiB and 471,789 files, below its 500,000-file
  soft quota.
- Final scratch usage: 71.92 GiB and 474,031 files. Scratch remains above its
  300,000-file soft quota but below the 500,000 hard limit with grace active;
  this task performed no install or download.

## Residual risk and follow-up

- A post-commit purge failure intentionally leaves a logged quarantine orphan.
  There is no background orphan GC in this slice; operator audit/GC remains a
  follow-up.
- Lock files are stable and persistent per content path. A future bounded lock
  metadata cleanup may be useful for very high lifetime cardinality.
- If a database commit succeeds remotely but reports an ambiguous client-side
  failure, the generic SQL transaction interface cannot prove the outcome.
  The implemented contract follows the required rollback-restore behavior.
- `download_all_files` still scans global public artifact roots; this was
  explicitly out of Task 12E scope and is unavailable for private collections.
- Existing deprecation warnings from Gradio, Pydantic, LangChain, and optional
  backends remain non-blocking and are not introduced by this task.

Task 12E2 verdict: **COMPLETE**. The shared-source safety invariant, exact
artifact cleanup, failure retry behavior, and package gates are green.
