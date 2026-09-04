# MARA Quality Hardening Checkpoint: Task 12E1

Date: 2026-07-11

## Frozen state

- Worktree: `/mnt/scratch/users/tbczhang/projects/MARA-quality-hardening`
- Branch: `codex/mara-quality-hardening`
- Last production/test commit: `448632d security: bind artifact identity and retention`
- Review range: `239f7df..448632d`
- Frozen review package: `.superpowers/sdd/review-239f7df..448632d.diff`
- Current task: Task 12E1 artifact production/publication and single-file download
- Status: **IN PROGRESS / NEEDS FIXES**
- Task 12E2 shared `Source.path` lifetime work has not started.

## Fresh checkpoint evidence

Commands were run from the worktree with the existing fastscratch environment.

- Task 12E1 six-file pytest gate: `84 passed, 6 warnings in 6.51s`, exit 0.
- Changed-Python hygiene: `No codebase hygiene ratchet violations.`, exit 0.
- `git diff --check 239f7df..448632d` and current `git diff --check`: exit 0.
- Full changed-file pre-commit: exit 1. All earlier hooks passed, then mypy failed at
  `libs/ktem/ktem_tests/test_file_artifact_manifest_bounds.py:95` because the test
  still constructs `ManifestArtifact(path=...)` after the held-fd type change.
- Spec/code-quality reviewer: **Needs fixes**, no Critical, two Important.
- Independent security reviewer: **Needs fixes**, no Critical, two Important plus the
  same quality-gate failure.

## Blocking findings

1. Parse-cache keys do not bind pathname-derived parsing context. Equal bytes with
   different extensions share a key even though the shared `UnstructuredReader`
   selects MIME/partition behavior from the suffix. This can reuse wrong text/content
   and artifact sidecars across requests.
2. `MAX_GLOBAL_SCAN_ENTRIES` is currently a per-directory limit, not one budget for
   the complete retention traversal. A hostile/corrupted tree can cause approximately
   `512 x 512` workspace visits under the global lock. A stale workspace containing a
   child directory is treated as removed even though it remains on disk, so it is not
   counted against capacity.
3. The manifest-bound test double is stale and blocks the required mypy/pre-commit
   gate even though pytest does not execute that resolver.

## Confirmed closed in Task 12E1

- Exact `file_id` plus generation artifact namespace and exact manifests.
- Server-side owner authorization before single-file ZIP/simple-HTML export.
- Configured-root and child descriptor walking with no symlink following.
- Hardlink, pathname-swap, unlink-swap, growth/shrink, and equal-length same-inode
  mutation rejection through held descriptors, metadata identity, and SHA-256.
- Manifest schema/path/count/byte limits and portable archive-name collision checks.
- Producer atomic writes, immutable generations, writer Future ordering, and failure
  propagation before manifest publication.
- Normal active/pending/ready lease reclamation, 128-output admission, and preservation
  of the 60-second browser fetch window.
- Unsupported platforms import successfully and fail closed when secure operations are
  invoked.
- `MARA`/`MARA-cli`, DB/session shapes, and the Gradio two-output/event ABI are
  unchanged; the hygiene baseline was not raised.

## Resume sequence

1. Use TDD to add deterministic RED cases for equal-byte/different-extension cache
   isolation, one shared retention scan budget, and failed stale-workspace removal
   remaining capacity-accounted. Fix the stale resolver double in the same test-only
   wave and record the existing mypy failure as RED evidence.
2. Commit the tests before production changes.
3. Implement the minimum cache-key/path-metadata isolation and retention-budget/removal
   accounting changes. Do not start Task 12E2 or broaden public behavior.
4. Re-run the expanded Task 12E1 gate, changed-file hygiene, full changed-file
   pre-commit, and `git diff --check`.
5. Update `task-12e1-report.md`, generate a new immutable review package, and obtain
   clean spec/code-quality plus security re-reviews.
6. Only then mark Task 12E1 complete and begin Task 12E2.

## Whole-plan position

- Top-level Tasks 1 through 11: complete.
- Task 12: in progress. Completed slices are 12A, 12B, 12C1, and 12C2; 12E1 is the
  active slice. Remaining after E1 are 12E2, 12F, 12G, and 12D.
- Task 13 full verification, formatting-only cleanup, and risk rescan: pending.
- Tracked execution slices: 18 complete of 24 total (`75%` by unweighted slice count).
  This is a progress indicator, not an effort-weighted forecast.

## Storage state

- `.venv` remains a symlink to `/mnt/fastscratch/users/tbczhang/envs/mara`.
- No repository-root `data/`, `datasets/`, or `outputs/` exists.
- Fastscratch inode use: `471893 / 500000` soft limit.
- Scratch inode use: `473370 / 300000` soft, `500000` hard; grace active.
- No dependency install, model call, dataset sync, or large download was performed.

Both filesystems remain under significant inode pressure. Resume with the existing
environment and avoid new installs or high-file-count operations.
