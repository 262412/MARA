# Task 12E1 Artifact Production and Single-File Download Report

> Final status (2026-07-12): **COMPLETE / APPROVED** at code commit `b1a4fc9`.
> All checkpoint blockers and the subsequent PathLike-metadata finding are fixed.
> The final frozen package received Approved verdicts for specification, code quality,
> and security, with no remaining Critical or Important E1 finding.

## 1. Status and commits

Task 12E1 and its filesystem/security review fixes are implemented as independent
tests-first/production/verification commits on base
`e9f12e7297ce508b0b90ea35f7029799bf7007eb`:

- `bd21d19 test: specify file export artifact isolation`
- `9f1971a security: isolate file export artifacts by source id`
- `35fff42 style: satisfy artifact isolation verification hooks`
- `a4e6050 test: expose artifact filesystem race conditions`
- `e78ea53 test: specify artifact review hardening`
- `ed1b263 test: correct generation and pending writer probes`
- `1e25154 security: harden artifact generation and downloads`
- `6d27cda test: expose artifact re-review gaps`
- `a75fd20 security: preserve exact cached export artifacts`
- `2af5106 test: expose artifact retention and identity gaps`
- `dbe9bca test: cover lifecycle platform and pending leases`
- `448632d security: bind artifact identity and retention`
- `59b2756 test: expose remaining artifact isolation gaps`
- `751bddf test: bound valid retention traversal`
- `398c40f test: distinguish retention capacity rejection`
- `baa55b5 security: isolate parse context and bound retention`
- `632ff17 test: expose pathlike parse metadata leak`
- `b1a4fc9 security: replay pathlike parse metadata`

This slice covers artifact production/publication and single-file ZIP/simple-HTML
consumption only. It does not change shared physical-source deletion or `Source.path`
reference counting; those remain blocking Task 12E2 work. It also does not include
C2 preview/KG, notebook, admin, browser/CSP, Settings, CLI, or public bulk-download
changes.

## 2. RED to GREEN evidence

The first RED commit added the nine cases required by the Task 12E brief in
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

The security review RED commits then added deterministic coverage for descriptor
TOCTOU races, hard links, root/namespace symlinks, atomic producer replacement,
bounded/strict manifest parsing, immutable generations, parse-cache hit/miss artifact
replay, pending/failed quick-index writers, and download workspace cleanup/retention.
Against the first implementation the complete review gate produced:

```text
39 failed, 12 passed, 3 warnings in 7.76s
```

Two RED self-review corrections were committed before production: the fake pipeline
now writes the random generation supplied by `IndexPipeline.stream`, and the pending
writer test uses an observed `Future` plus `Event` to prove finalization has actually
blocked. After `1e25154`, the same review gate produced:

```text
51 passed, 3 warnings in 6.54s
```

Re-review then added exact cache-sidecar/runtime-metadata isolation, held-file
size/fstat, and real-payload lifecycle probes. The targeted RED evidence was
`6 failed, 3 passed`; the failures were the intended MHTML multipart/Azure span
artifact drift, legacy/no-sidecar reuse, runtime metadata leakage, and held-leaf
growth/shrink acceptance. After `a75fd20`, the expanded complete gate produced:

```text
58 passed, 6 warnings in 6.88s
```

The final review wave added neutral cached-parse context, equal-length artifact and
manifest mutation, configured-root ancestor symlinks, fixed/portable manifest paths,
background `BaseException`, cleanup masking, cross-file retention, live/stale leases,
global capacity, markerless crash residue, and missing-`fcntl` coverage. Against
`a75fd20`, the focused five-file gate produced:

```text
22 failed, 50 passed, 5 warnings in 7.69s
```

After `448632d`, the expanded six-file Task 12E1 gate produced:

```text
84 passed, 6 warnings in 6.62s
```

The 2026-07-11 checkpoint first preserved the existing type-check failure with the
same dependency-visible file set used by the changed-file hook:

```text
uv run --python 3.10 pre-commit run mypy --files \
  libs/kotaemon/kotaemon/artifact_types.py \
  libs/kotaemon/kotaemon/artifact_namespace.py \
  libs/ktem/ktem_tests/test_file_artifact_manifest_bounds.py

test_file_artifact_manifest_bounds.py:95: error: Unexpected keyword argument "path"
Found 1 error in 1 file (checked 3 source files)
```

Passing only the test file made the imported implementation an ignored import and
therefore did not reproduce the error; including the two defining modules exposed the
stale `ManifestArtifact(path=...)` constructor exactly. Commit `59b2756` replaced it
with a type-correct fail-if-called sentinel and added the remaining regressions. The
focused RED command covered the new parse-context file, the shared lifecycle budget,
failed-removal capacity accounting, and the manifest sentinel. It produced:

```text
5 failed, 1 passed in 6.33s
```

The intended failures were: equal-byte `.html`/`.txt` cache collision; same-context
reuse leaking the first `file_name`; a per-directory rather than tree-wide scan
budget; and stale-active plus expired-ready child-directory residue disappearing from
capacity. The manifest count sentinel was the one passing case.

Controller self-review then found two adjacent boundary cases without weakening the
original assertions. With the first partial production diff present, the next RED
command still produced `3 failed in 6.29s`: valid ready entries were enumerated again
during pruning, and regular-file corruption at the file-id and request levels was
silently skipped. The strengthened distributed 128-output capacity test separately
produced `1 failed in 6.12s` because the underlying cause was `Download lifecycle scan limit exceeded` rather than the required capacity rejection.

After `baa55b5`, the unchanged focused assertions produced `9 passed in 5.38s`. The
expanded eight-file Task 12E1 plus parse-cache gate then produced:

```text
97 passed, 6 warnings in 5.99s
```

The next spec re-review identified one remaining Important metadata shape: Azure and
Docling-style readers can store `Path`/`os.PathLike` values in `file_path` or `source`.
The cache role detector compared only strings, while `_json_safe` serialized the miss
path to a string, so a same-context hit could expose the first pathname. Commit
`632ff17` added one parameterized production-shaped regression for both keys. The RED
command produced:

```text
2 failed in 2.60s
```

Both cases confirmed a real cache hit (`reader.calls == 1`) but received `first.txt`
instead of the current `second.txt`. After `b1a4fc9`, the parameterized test produced
`2 passed in 2.16s`, the complete path-context file produced `4 passed in 1.95s`, and
the expanded eight-file gate produced:

```text
99 passed, 6 warnings in 5.77s
```

## 3. Artifact and manifest layout

The database `file_id` is now the sole artifact namespace token. The original
filename remains only in human-readable filenames inside that namespace:

```text
KH_CHUNKS_OUTPUT_DIR/<file_id>/<generation>/<original-stem>_<chunk-index>.md
KH_MARKDOWN_OUTPUT_DIR/<file_id>/<generation>/<original-stem>.md
KH_ZIP_OUTPUT_DIR/manifests/v1/<file_id>/manifest.json
KH_ZIP_OUTPUT_DIR/downloads/<file_id>/<request-uuid>/download-<request-uuid>.zip
KH_ZIP_OUTPUT_DIR/downloads/<file_id>/<request-uuid>/download-<request-uuid>.html
```

`kotaemon.artifact_namespace` remains the compatibility facade. The reviewed
implementation splits real responsibilities across focused kotaemon modules for
identifiers, secure descriptor-relative filesystem operations, producers, manifest
parsing/publication, immutable pipeline generations, download workspaces, shared ZIP
path normalization, and held-artifact types. This keeps kotaemon producers from
gaining a reverse dependency on the ktem application/UI package without growing a
new monolith.

The version-1 manifest contains exactly:

```json
{
  "version": 1,
  "file_id": "<file_id>",
  "entries": [
    {
      "kind": "chunks",
      "relative_path": "<file_id>/<generation>/<name>"
    },
    {
      "kind": "markdown",
      "relative_path": "<file_id>/<generation>/<name>"
    }
  ]
}
```

Each stream assigns a fresh generation before parse-cache lookup. When a parse cache
is configured, reusable parsing runs with `extra_info=None`; user, layout, and
generation values therefore cannot affect cached text/content or parse policy. The
key now also binds the normalized pathname-derived parse context: case-folded suffix
and the effective MIME inferred through the same `mimetypes` policy used by the shared
`UnstructuredReader`. It intentionally does not bind the full pathname, so equal bytes
with the same parse context remain reusable while equal bytes under different
extensions cannot share text, content, or artifact sidecars.

Internal parse payload version 3 removes only metadata values proven to derive from
the miss pathname (`file_name`/`filename` and `file_path`/`source` roles), then replays
those roles from the current path on a hit before current `extra_info` is applied.
Role comparison normalizes strings, bytes, and `os.PathLike` values with
`os.fsdecode`, covering production `Path` metadata without changing string behavior.
Same-context reuse therefore cannot disclose the first request's path identity. The
generation token is removed before docstore/vector persistence and passed explicitly
to the chunk writer. The no-cache loader path preserves its existing runtime-context
behavior.

Versioned internal cache sidecars preserve the exact MHTML first-part and Azure
pre-span-removal markdown bytes. MHTML and Azure artifacts are identical on misses and
hits without repeating Azure network analysis, and old/no-sidecar reader caches are
not reused. Manifest publication scans only the current generation.

Entries are deterministically ordered by kind and path. In quick-index mode,
`finish_and_publish_artifacts` waits on the actual background writer `Future`,
propagates its exception, then calls the existing `finish` operation and publishes.
Publication writes a unique same-directory temporary file through a held directory
descriptor, flushes and `fsync`s both file and parent directory, then atomically
replaces the exact manifest. A pending or failed writer and a failed `finish` cannot
publish a manifest or reach the success event.

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
file-id namespace, a configured root or component is a symlink, the target is not a
single-link regular file, or two entries collide under the shared portable ZIP-member
normalization. Parsing is bounded to 1 MiB, 2,000 entries, 1,024-character relative
paths, and 2 GiB of artifact bytes. Empty entries, boolean versions, duplicate JSON
keys, invalid UTF-8, excessive JSON recursion, explicit empty/dot path segments, and
non-regular targets are rejected. Missing/invalid manifests and unauthorized probes
use the same non-disclosing reindex-required Gradio error.

Consumer traversal opens trusted `/` and walks every configured-root ancestor and
namespace component descriptor-relatively with `O_NOFOLLOW|O_DIRECTORY`; final-only
and ancestor symlinks fail closed. Each leaf remains open until copied through
`ZipFile.open`, so pathname swaps cannot redirect the archive. Initial identity binds
regular type, single link, device, inode, size, mtime, ctime, and SHA-256. The copy
reads exactly the bounded byte count and revalidates metadata plus digest before,
during, and after streaming, rejecting equal-length rewrites, growth, shrinkage, early
EOF, trailing bytes, and unlink swaps. Manifest bounded reads receive the same
post-read metadata and byte-identity validation. The callback never validates a
`Path` and then reopens it.

The deleted `_download_outputs_for(file_stem)` global scan has no compatibility
replacement. Legacy shared-root artifacts are untrusted cache and require reindexing.
ZIP members intentionally use `chunks/...` and `markdown/...` prefixes so equal
basenames cannot replace each other. A repository documentation search found no
documented legacy archive-member layout requiring a separate user guide/release-note
edit; this report records the intentional surface change.

`download_single_file_simple` also authorizes the file server-side before writing and
uses the same file-id/request isolation. ZIP and HTML outputs use an `.active` request
workspace, unpredictable exclusive temporary file, atomic final replacement, and a
durable `.ready` marker. Failures remove the temporary/request directory. Bounded/TTL
retention now holds a POSIX `flock` lease on each live `.active` marker and one global
cross-process lifecycle lock around scan/prune/count/admission. Any download activity
performs one traversal-budgeted scan across every file ID, reclaims expired ready
outputs and unlocked stale active/markerless crash residue, and preserves
old-but-locked live workspaces. The `513`-entry default is the explicit valid-tree
bound: one lifecycle lock plus file-id, request, marker, and payload for each of the
128 hard-cap records. Already enumerated ready entries are reused during pruning, so
cleanup does not spend the same budget twice.

Removal returns an explicit removed/retained result. Child-directory or other
non-removable residue stays in the record set and counts against the hard cap;
corrupted non-directory entries at either the file-id or request level fail closed
instead of disappearing from accounting. Per-file and global limits prune only ready
paths outside the 60-second browser fetch window; if protected/live/retained paths
fill global capacity, admission fails without revoking a returned path. Toggling an
already-enabled download off authorizes, returns the existing two-output shape, and
creates no unreturned server output. Its positional inputs and labels remain
unchanged.

Producer writes likewise open configured roots and namespace chains without following
any ancestor symlink, write unpredictable `O_EXCL` temporaries through held generation
directory descriptors, `fsync`, and atomically replace the leaf. Predictable leaf
symlinks and generation-directory swaps therefore cannot overwrite or redirect victim
files. Artifact and ZIP member components reject control/NUL, non-NFC, Windows
reserved/drive-like, trailing-dot/space, and portable-normalization collision forms;
manifest artifact paths are exactly `file_id/generation/leaf`.

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

The implementation files are grouped by responsibility:

- artifact facade/types/identifiers/path normalization:
  `artifact_namespace.py`, `artifact_types.py`, `artifact_identifiers.py`, and
  `artifact_paths.py`
- secure producer/consumer/lifecycle services: `artifact_secure_fs.py`,
  `artifact_producers.py`, `artifact_manifest.py`, `artifact_downloads.py`, and the
  focused global `artifact_retention.py` lease/admission service
- pipeline/cache coordination: `artifact_pipeline.py`, `artifact_cache.py`,
  `indices/parse_cache.py`, `indices/vectorindex.py`, both markdown-producing loaders,
  and ktem `index/file/pipelines.py`
- download/archive integration: ktem `index/file/_scoped_page.py` and
  `index/file/archive.py`

The focused test files are `test_file_export_isolation.py`,
`test_file_artifact_security_fs.py`, `test_file_artifact_manifest_bounds.py`,
`test_file_artifact_generation.py`, `test_file_artifact_quick_index.py`, and
`test_file_download_lifecycle.py`; the focused kotaemon parse-context coverage is
`tests/test_parse_cache_path_context.py`.

`_download_events.py` was characterized but not modified, preserving component inputs,
two outputs, labels, branches, and event order.

## 6. Hygiene and verification

Fresh post-review commands and results at `b1a4fc9`:

- expanded eight-file Task 12E1/cache pytest gate: `99 passed, 6 warnings`, exit 0
- `scripts/check_codebase_hygiene.py` over all 25 changed Python files in
  `239f7df..b1a4fc9`: `No codebase hygiene ratchet violations.`, exit 0
- full pre-commit over all 28 changed files in `239f7df..b1a4fc9`: hygiene, file
  checks, secret/large-file checks, black, isort, flake8, autoflake, prettier, mypy,
  and codespell all passed, exit 0
- `git diff --check 239f7df..b1a4fc9` and the current working-tree
  `git diff --check`: exit 0
- the unchanged kotaemon package gate from `baa55b5` was not repeated for the narrow
  metadata-type normalization: `344 passed, 8 skipped, 92 warnings`, exit 0
- negative single-download callback scan: `_scoped_page.py` has no legacy
  `_download_outputs_for`, artifact-root `os.listdir`, stem, prefix, or substring
  discovery; the separate retention service intentionally performs a bounded global
  workspace scan under its lifecycle lock; exit 0
- negative producer scan gate: no direct filename-stem write to a shared configured
  chunks/markdown root; exit 0

No hygiene baseline was refreshed or increased. The first implementation hygiene run
correctly rejected growth in existing baseline files (`vectorindex.py`, Azure loader,
and `pipelines.py`). The review implementation also initially detected growth in
`IndexPipeline.handle_docs`; background-writer scheduling was extracted at a real
pipeline-coordination boundary. The final `pipelines.py` is 986 lines versus its
990-line baseline, the former 357-line `artifact_namespace.py` is now a 125-line facade,
and every new responsibility module/function remains within the 600/80 budgets. The
524-line retention module is below its 600-line budget, and the expanded security
fixtures remain readable legitimate test code rather than being compressed to satisfy
line counts.

Non-final errors and remediation:

- initial GREEN was `6 passed, 4 failed`; all four paths were already correctly
  fail-closed, but the generic message used uppercase `Reindex` while the security
  contract asserted lowercase `reindex`; production copy was normalized
- initial hygiene failed on baseline growth; responsibilities were extracted without
  updating the baseline or compressing fixtures
- first production pre-commit found an unused `Path` import after extraction;
  autoflake removed it and the fresh run passed every hook
- review RED self-audit found a fake fixed-generation producer and an already-complete
  writer double; both tests were corrected in `ed1b263` before production
- first review GREEN was `50 passed, 1 failed` because a reused vector writer kept a
  global chunk counter across file generations; the counter is now generation-scoped
  and the fresh review gate is `51 passed`
- first review hygiene/pre-commit pass found baseline growth, formatting, import
  ordering, and two mypy issues; responsibility extraction and narrow type fixes made
  the fresh full hook run pass without baseline changes
- re-review found cache-hit artifact reconstruction was lossy, first-run runtime
  metadata remained in the generic cache, held leaves could change size before copy,
  and lifecycle fixtures did not carry real payloads/ages; `6d27cda` locked each gap
  in RED before `a75fd20` added versioned exact sidecars, full runtime-key exclusion,
  bounded/fstat-verified copying, and real-payload TTL/count/fetch-window evidence
- final review found equal-length byte identity, configured-root ancestors,
  parse-affecting runtime context, stale/crashed workspaces, cross-file/global bounds,
  and fetch-window hard-cap issues; `2af5106`/`dbe9bca` locked these in RED before
  `448632d` added digest binding, trusted-anchor descriptor walking, neutral parsing,
  POSIX live leases, global backpressure, and the low-cost review minor fixes
- checkpoint re-review found pathname-derived cache policy was still absent, the
  lifecycle budget reset per directory, failed removals vanished from capacity, and
  the manifest resolver double was stale; `59b2756` captured all four behaviors before
  `baa55b5` bound suffix/MIME, replayed current path metadata, shared the budget, and
  retained removal residue
- controller self-review found valid pruning could enumerate ready workspaces twice,
  corrupt tree entries could be skipped, and the original `512` default was one entry
  short for 128 distributed valid outputs; `751bddf`/`398c40f` preserved these as RED
  before enumeration reuse, non-missing corruption fail-closed, and the explicit
  `1 + 4 * 128 = 513` bound were committed
- spec re-review found `Path`/`os.PathLike` metadata bypassed string-only path-role
  comparison and serialized the first request path into same-context hits; `632ff17`
  reproduced both `file_path` and `source` leaks before `b1a4fc9` normalized path-like
  values with `os.fsdecode`

Durability ledger: `os.replace` makes the new leaf visible before the following parent
directory `fsync`. If that `fsync` fails, the operation reports failure even though the
new name may already be visible. A safe generic rollback cannot guarantee restoration
after an I/O durability failure, so the implementation fails the indexing/download
operation and never claims publication success; this residual visibility ambiguity is
recorded rather than hidden behind an unsafe rollback.

Warnings are existing dependency deprecations/user warnings from Pydantic,
BeautifulSoup/lxml, pypdf cryptography, LangChain, Gradio/FastAPI, Milvus/Qdrant, and
related test doubles; none is a new failure from this slice.

## 7. Storage and residual risk

Final storage preflight evidence:

Fresh commands were `pwd`, `readlink -f .venv`, `.venv/bin/python` executable/version
inspection, `printenv` for cache/runtime variables, repository-root checks for
`data`/`datasets`/`outputs`, and `lfs quota -h -u tbczhang` against both
`/mnt/fastscratch` and `/mnt/scratch`.

- repo: `/mnt/scratch/users/tbczhang/projects/MARA-quality-hardening`
- `.venv`: symlink to `/mnt/fastscratch/users/tbczhang/envs/mara`
- Python: fastscratch CPython 3.10.20
- cache/runtime variables: fastscratch; pre-commit cache: scratch
- repo root: no `data/`, `datasets/`, or `outputs/`
- fastscratch: approximately `295.8 GiB`, `471791 / 500000` soft inode quota
- scratch: approximately `71.9 GiB`, `473377 / 300000` soft and `500000` hard inode quota; still in
  grace

Tests used the configured temporary pytest runtime. No dependency install, model call,
dataset sync, indexing of user data, or large download occurred.

Residual/follow-up work:

- Task 12E2 must implement the shared `Source.path` lifetime lock/refcount/quarantine
  sequence and file-id artifact deletion. E1 does not make physical blob deletion safe
  and does not claim the full Task 12E shared-source invariant.
- Legacy global artifacts remain on disk until reindex/manual follow-up, but are never
  consumed by the single-file download path.
- A failed producer/index run can leave an unmanifested file-id namespace; it is not
  downloadable. Cleanup belongs with E2 deletion or a later orphan-GC audit.
- Explicit parse-affecting `load_kwargs` overrides are not introspected automatically
  by the cache key; a caller using them must mirror their stable values into
  `reader_policy`. Current E1 callers do not pass such overrides, so the reviewer
  classified this as a non-blocking API-hardening Minor.
- Ready/stale workspace expiry is intentionally lazy. The lifecycle scan now has one
  `513`-entry traversal budget sized for the full valid hard-cap tree. Trees beyond
  that bound and non-missing corrupt entries fail closed. A child-directory residue
  is not recursively deleted; it remains capacity-accounted until external/operator
  cleanup, avoiding an unsafe recursive deletion policy.
- Secure descriptor traversal requires POSIX `dir_fd`/`O_NOFOLLOW`; cross-process
  retention additionally requires `fcntl.flock`. Windows or unsupported runtimes keep
  the modules/UI importable but file export fails closed at invocation. Adding a safe
  non-POSIX implementation is follow-up work, not an unsafe compatibility fallback.
- Artifact identity hashing adds a full validation pass (and a post-copy pass) over
  downloadable artifacts. The 2 GiB total bound limits abuse, but very large exports
  trade additional I/O for byte-identity guarantees.
- The focused and kotaemon package gates did not run browser/live Gradio, model, or
  LibreOffice integration; event ABI/order is protected by existing browser-free
  contracts.
- Both scratch and fastscratch inode pressure remain operational risks for future large
  runs.

## 8. 2026-07-12 checkpoint resolution and re-review state

The `448632d` checkpoint's three blocking findings were resolved at `baa55b5`:

1. Parse keys bind normalized suffix and effective MIME. Equal bytes under different
   extensions miss independently, including text/content/artifact sidecars. Equal
   bytes with the same parse context may hit, but cached pathname metadata is removed
   and replayed from the current path before runtime metadata is applied.
2. Retention creates one shared budget for root/file-id/request/workspace enumeration
   and reuses ready-entry names during pruning. The default `513` bound admits a full
   valid 128-record distributed tree to the capacity decision. Removal returns success
   or retained; child-directory residue remains in the record/capacity set, while
   non-missing corrupt file-id/request entries fail closed.
3. The manifest-count resolver is a type-correct sentinel that fails if resolution is
   reached. The dependency-visible mypy command and the complete changed-file hook are
   green.

The subsequent spec re-review's sole Important finding is resolved at `b1a4fc9`:
`file_path`/`source` role detection now normalizes strings, bytes, and `os.PathLike`
values before comparing them with the current path. Both production-shaped Path
metadata cases preserve the same-context cache hit and replay the second request path.
Suffix/MIME keying and payload version 3 are unchanged; the full pathname is still not
part of the key.

The review package was generated with ordinary Git commands from the frozen checkpoint
review base through the final production commit:

```text
.superpowers/sdd/review-239f7df..b1a4fc9.diff
SHA-256 da5347b7d581cca6278d21823433949dd247d67e8c705572e88a331f646a93cc
5,498 lines; 201,981 bytes
```

The package is ignored mechanical review output and is not part of the source commit.

Final review verdicts:

- specification: **Approved**
- code quality: **Approved**
- security: **Approved**
- Critical findings: none
- Important findings: none

Controller-side final re-verification produced `99 passed, 6 warnings`; the hygiene
ratchet and the complete 28-file pre-commit set, including mypy and secret checks,
passed again. The remaining non-blocking items are explicit parse-affecting
`load_kwargs` requiring matching `reader_policy`, lazy TTL cleanup, child-directory
residue requiring operator cleanup, and the documented replace-then-fsync durability
ambiguity.

Task 12E1 verdict: **COMPLETE / APPROVED**. Task 12E2 shared `Source.path` lifetime
work remains the next task and has not started at this commit.
