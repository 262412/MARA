# Safe-refactor status

## Current review point: R5-C/B1 browser closeout

Branch: `codex/r0-r1-safe-refactor`. This round baseline: `bccae366647f0e3fcb4a9df2f48f90827c09ecfb`;
preceding frozen source/tests/package inputs: `ae31c731b46bbc677ca64913c3ce2bdf9f62586e`.
Original R5-C baseline: `703eef5fb6e597e049cc49d527d780764730afe4`;
independently accepted R5-B source/tests: `26e13211963618a5542eacb0f7aee36e59510b16`;
fixed original Dev: `adab3f4d8f221e3620494fab0a24ef8e5557d12a`.

**R5-C 阻塞关闭，限定验证通过，等待 R5 独立收口审查。**
Final frozen source/test/harness SHA: **`41274852f1fda541b3162d5ae39a43beb8e92605`**. R5-C is **not ACCEPTED**.
The user's accepted R1–R5-B, L1/I1 and W1/W2 scopes remain accepted within their
agreed boundaries. All prior failed attempts, fixes and same-source double 36/36
evidence remain retained. S1/PCRE2 are **OPEN**, G0's exact exception is unchanged,
and merge/release remain **NO-GO**. Stop at R5 review; no R6, upgrade, merge,
deployment or release.

Evidence parent: `D:/PythonProject/MARA-refactor-review-20260910-01a086ff/`.
`r5c-b1-closeout/` holds causal diagnostics and the retired 43ca5391 attempt;
`r5c-b1-ci/` preserves its cancelled CI. `r5c-b1-verification/` and
`r5c-b1-final-ci/` hold the final same-source matrices, local gates, build,
coverage and full CI receipts. All original `r5c-lifecycle/`, `r5c-source-ci/`,
`r5c-final-verification/`, `r5c-review-verification/`, `r5c-review-ci/`,
`r5c-contract-verification/` and `r5c-contract-ci/` evidence remains in place.

### Owner, contract, evidence and status

| Scope            | Owner and boundary                                                       | Contract and evidence                                                                                                                              | Status                                                     |
| ---------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| R5-A             | Existing file-deletion coordinator and external-storage cleanup          | Accepted deletion fault matrix and external-store failure/ownership boundaries retained; platform failures remain separately classified            | ACCEPTED within prior reviewed scope                       |
| R5-B             | Existing ingestion, writer/iterator/ZIP and Source lifecycle services    | L1 Source leases, I1 index identity, writer cancellation/failure and two-owner ZIP/indexing scenarios re-exercised; original double 36/36 retained | ACCEPTED by user within agreed scope                       |
| W1/W2            | Existing browser observer and group event chain                          | Operation-identity counterexamples and close-before-list order unchanged; full Node/browser regressions                                            | ACCEPTED by user                                           |
| C1 I/O           | `knowledge_graph_cache` behind both original graph services              | Atomic snapshot, corrupt-cache diagnosis, old method/patch entrypoints and normal JSON envelope                                                    | Limited verification passed; pending independent R5 review |
| C1 lifetime      | `knowledge_graph_lifetime`, original Source lease and Conversation lease | Current authorization plus source/index/scope snapshots; stale/ABA/session/source/reindex publication refusal; draft is not persisted              | Limited verification passed; pending independent R5 review |
| C2 conversion    | `_runtime_notebook`, `artifact_service`, existing Session services       | Existing normalize/merge, IDs, timestamps, copy/serialization and NotebookAccessError semantics                                                    | Limited verification passed; pending independent R5 review |
| C2 commit        | `notebook_persistence` and `conversation_lifetime`                       | Independent Sessions/processes, both Notebook and chat write boundaries, fresh reload under short leases; no generic deep merge                    | Limited verification passed; pending independent R5 review |
| C3 producer      | `DownloadWorkspace`, manifest and existing FD interfaces                 | Own temporary/active/ready/payload handles; partial allocation/copy/publication/cancellation and primary/secondary exception tests                 | Limited verification passed; pending independent R5 review |
| C3 consumer      | `download_scope`, `download_http`, `artifact_transfers`                  | Current server identity and Source scope at HTTP claim, pinned payload FD and transfer lease through response completion/disconnect                | Limited verification passed; pending independent R5 review |
| C3 retention     | Existing `artifact_retention`                                            | Existing TTL/capacity/scan budgets, live-transfer refusal, only owned unused resources; no background or root cleanup                              | Limited verification passed; pending independent R5 review |
| B1 browser proof | Existing App harness, read-only frontend observer and production guard   | Exact event delivery/coalescing evidence, deterministic guard counterexamples, same-source double 37/37                                            | Blocker closed; pending independent R5 review              |

### Actual structure and preserved boundaries

The inherited R5-C source/test range changes 46 files, including 23 production/package-input files. This B1 follow-up changes ten test/harness files and no production/package-input file. New production resources: `libs/kotaemon/kotaemon/artifact_transfers.py`, `libs/ktem/ktem/docqa/conversation_lifetime.py`, `libs/ktem/ktem/docqa/knowledge_graph_cache.py`, `libs/ktem/ktem/docqa/knowledge_graph_lifetime.py`, `libs/ktem/ktem/docqa/notebook_persistence.py`, `libs/ktem/ktem/index/file/download_http.py`, `libs/ktem/ktem/index/file/download_http.pyi`, `libs/ktem/ktem/index/file/download_scope.py`. Production responsibility moves are limited to cache I/O,
cache publication/authorization, short Conversation commits and download claim/
transfer ownership. `knowledge_graph_cache.py` is the shared existing-method
delegate; `notebook_persistence.py` is a narrow Session/authorized-load/commit
helper. `conversation_lifetime.py` reuses the L1 locking implementation.
The C1 and C2 mechanical extractions are separate commits from behavior fixes.

The original graph services retain their algorithm bodies, builder/renderer,
normal structures and `_get_storage_path`, `_load_cached_state`,
`_save_cached_state` seams. The runtime cache reader now carries the current
principal into its existing read path. A cached graph never supplies authority.
`graph-method-boundary-proof.json` compares every original service method:
all original signatures and every method body outside the named cache I/O and
build/view publication methods are unchanged ASTs.
`_runtime_notebook`, `artifact_service` and the original Session service remain;
their public signatures and record conversion functions are preserved.
`artifact_service`, graph builders, L1/I1 production, W2 event order, safe FD
path implementation, dependency locks, security/hygiene baselines, coverage
collectors/floors and required jobs have unchanged Git blobs, recorded in
`frozen-scope-protection.json`.

The Gradio output adapter retains the existing DownloadButton frontend and
callback entrypoints but points it at a scoped HTTP route. Its generated `.pyi`
is shipped as a runtime package resource, following the existing `File` component
pattern. It is generated interface data, not a second service implementation.
No shared backend is closed and no existing backend policy is replaced.

### C1: atomic bytes and current publication are separate contracts

Characterization and red evidence include `c1-cache-baseline-red`,
`c1-interleavings-red`, `c1-runtime-read-red` and `c1-cache-permission-red`.
The original implementations exposed partial files, accepted unusable top-level
JSON, allowed older independent builders to publish late, and exposed a runtime
cache read without sufficient current conversation authorization.

The fix writes an exclusive sibling temporary, flushes/fsyncs/closes it, then
replaces the snapshot. Corrupt JSON is diagnosed and treated as unusable;
permission and other filesystem errors propagate. This atomic replacement alone
is not the concurrency protocol. Short Source/Conversation leases re-read current
SQL state. A per-conversation request receipt rejects superseded builders,
including A→B→A. Source version includes current index relation IDs, and cache
publication has a separate snapshot digest receipt. Publication rechecks source
and conversation deletion, reindex, ownership and changes to the selected scope
captured when that request began. Cache reads separately check current access,
source/index version, snapshot bytes and changes during their short read window.

Graph build/model work is outside those leases and SQL Sessions. Both original
services are tested with independent instances, same file/different sessions,
two users, draft, source/session deletion, reindex and late completion.
The cache is rejected at its disk/read boundary, independently of UI stale-output
guards. A failure after replacing the main snapshot but before its receipt can
leave new bytes on disk; the next read refuses them as unverified. This is not
reported as a multi-file rollback.

Historical caches are not swept or rewritten. The original sanitized cache name
mapping is retained, including its non-injective mapping for unusual historical
IDs; no historical ID migration is claimed. Legacy snapshots without a current
receipt are rebuildable/stale. The original graph algorithms are unchanged.

### C2: fresh short commits and actual multi-store outcomes

`c2-independent-sessions-red` demonstrates lost updates with genuinely independent
Sessions. The repair coordinates every directly participating Notebook and chat
JSON write boundary, including selected sources, export registration, artifact
deletion and conversation deletion. Each writer opens its own Session and reloads
the current row under the Conversation lease. It applies the existing domain
transform once and commits briefly; it does not merge arbitrary stale JSON.
Public conversation read access does not grant Notebook mutation/export access.

Lock order is sorted Source leases → optional content lease → Conversation lease
→ short SQL work when those boundaries are combined. Notebook-only changes take
the Conversation lease directly. No Session is shared between threads, and no
model call or worker join waits under a Source lock/SQL transaction. The process
contract is same host, same database identity and shared lease directory; the
independent process test demonstrates exclusion, unrelated-conversation progress,
preservation of both commits and release. Multi-host fencing is not designed or
certified.

`test_notebook_storage_pipeline.py` exercises real Markdown materialization,
the retained indexing pipeline, SQLite Source/Index relations, Lance documents,
Chroma vector IDs and Notebook backfill, then reload. It also runs actual artifact
export, registration and reload. Deterministic model inputs do not replace those
storage boundaries. Observed outcomes are explicit:

| Failing stage                                  | Materialized/exported bytes          | Source/index commit                                     | Notebook record                                        |
| ---------------------------------------------- | ------------------------------------ | ------------------------------------------------------- | ------------------------------------------------------ |
| Before note materialization                    | Absent                               | Absent                                                  | Original note retained                                 |
| Indexing stage failure                         | Note Markdown remains                | No successful Source in this injected path              | No indexed-source backfill                             |
| Notebook backfill commit                       | Note Markdown remains                | Source, document/vector rows and backend records remain | Backfill rolled back                                   |
| Session deleted after indexing                 | Note Markdown remains                | Source/index/backend records remain                     | Session remains deleted; late task cannot resurrect it |
| Export registration commit                     | Export remains with verified content | Not a Source operation                                  | Export entry absent after reload                       |
| Delete artifact record after successful export | Export remains                       | Unchanged                                               | Only selected Notebook artifact record removed         |

Earlier test-fixture errors (missing note title and wrong Chroma accessor) are
retained separately from the storage defects. Record deletion does not cascade
to Source rows, shared blobs or historical exports. No cross-storage rollback or
compensation platform is claimed.

### C3: generation, claim, transfer and retention

The red series covers partial workspace allocation, fdopen/marker/close failures,
manifest normalization after FD acquisition, duplicate-handle release, cancellation,
pruning while a ready payload is in use, and real Gradio/HTTP requests.
The original HTTP path returned copied output to another owner and after
Source deletion/revocation. A successful producer alone did not protect transfer.

New output carries a scoped ready receipt. The HTTP claim derives the principal
from server authentication, reloads Source access/version under its L1 lease,
then uses the existing safe FD operations. The claim pins payload and ready-marker
FDs; transfer holds a shared marker lease until GET/HEAD/range completion,
disconnect or send failure. It releases the Source lease before sending bytes.
Existing retention needs the exclusive marker lease and therefore cannot remove
an active transfer. New claims after deletion/revocation fail. An already
authorized pinned snapshot may finish after later deletion; the contract does
not promise mid-stream byte revocation.

HTTP claim lock order is Source → download lifecycle → nonblocking ready-marker
lease; retention does not acquire Source or Conversation locks. This verification
covers outputs issued by the current scoped pipeline. It makes no claim of
retroactive revocation/migration of historical export or Gradio cache copies.

| State          | Owner and release behavior                                                                                                             |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Generating     | Own request directory, active lease and temporary/payload FD; partial allocation and cancellation attempt all owned release boundaries |
| Awaiting claim | Published payload plus ready receipt; creation must finish before any transfer can acquire the marker                                  |
| In transfer    | Pinned payload and shared ready-marker lease; cleanup waits for unused resources without retaining Source/SQL locks                    |
| Expired        | New claim refused; original bounded request-driven retention may remove only an unused owned workspace                                 |
| Failed residue | Actual published/temp/marker state retained and diagnosed; cleanup failure never becomes a claim of successful rollback                |

The original constants remain: 24-hour ready TTL, 60-second ready fetch window
before capacity pruning, 600-second active TTL, 32 ready per file, 128 global
hard capacity and 513-entry scan
bound. No new background cleanup, root clear or cleanup of shared historical
outputs is added. Numeric FDs are invalidated before close attempts, so retries
cannot close a reused descriptor. All owned descriptors are attempted; secondary
close/cleanup failures are logged without replacing the primary failure.

POSIX executes real safe-dir-FD, flock, same-file concurrent generation, active
transfer, expiry and pruning tests. Linux HTTP integration uses the real Gradio
ASGI app and TestClient login/prediction/GET/HEAD/range routes, with actual payload
bytes and native FDs; cancellation/send-failure tests drive its ASGI response.
The complete interactive browser matrices run on native Windows; a successful
POSIX browser/TCP transfer is not claimed. Native Windows retains fail-closed
behavior where secure directory/lifecycle-lock capabilities are unavailable;
the browser checks a visible refusal and no unprotected link, and HTTP checks
owner capability refusal versus foreign/deleted-source denial. Eight new POSIX
cases are explicit Windows skips and execute in both Linux kotaemon jobs.
Windows tests do not relax path validation to manufacture successful downloads.

### Retained failed source and packaging repair

Source `553da46d2112b6aedd2aab40de06f682bc315314` passed its local/full Linux suites
and four wheel-install smokes but failed actual non-root container startup:
Gradio's metaclass could not create/read `download_http.pyi` in installed
site-packages. Its CI is retained at run `35624958574`; this is a new R5-C runtime
regression, not an old PCRE2 finding. Its partial browser matrix is not an
acceptance run. Already active batches completed and cleaned their owned roots;
remaining batches were stopped.

`205a3bba819bf13d0efc230f89e367e59ea9487f` records the failing read-only component
test before the fix. `33716dda50500ad027210f1decf5aaf6f5e76798` ships the generated
interface, with no HTTP/authorization/timing logic change. The targeted 19-test
green and subsequent full-source gates are separate evidence. The earlier outer
browser collector's GBK/UTF-8 decoding failure and its exact 133-versus-135 hash
guard correction are also retained; neither was a UI assertion failure or a
selective green retry.

At `33716dda`, the primary retained browser batch failed 1 of 12 records:
the PDF search input remained hidden after its single search-button click.
The other 11 records and all logs/screenshots remain; the failing run did not
record the exact pre-click initialization state, so that specific causal state
is not claimed as proven. A separate controlled full-App probe held PDF.js's
viewer module: the button was visible while initialization/document readiness
were false, the early click was ineffective, and a single click after readiness
opened search. Commit `5e4058c3f1200627dc609d17f585475ae0dd3a4f` adds an explicit
PDF initialization/document readiness wait before the existing click. Production
preview/PDF assets and search/source-switch assertions are unchanged. It is a
test precondition repair, with no repeated click, arbitrary sleep or blind retry.

The 33716dda Windows kotaemon run had a fifth failure, separate from its four
historical capability failures: an isolated child encountered an SSL EOF while
fetching the public tokenizer resource. Its full traceback is retained. A bounded
transport/hash check succeeded before a preregistered full run at 5e4058c3;
that complete run returned to the same four failure nodes/natures. No dependency,
application configuration or real user cache was changed to pass the check.

The first complete coverage artifact measured production-equivalent code at
551/620 R5-C incremental lines (88.87096774193549%), below the unchanged 90% gate.
The 5e4058c3 browser sequence was stopped at the next batch boundary after its
12/12 retained batch and successful owned cleanup; the following batch never
started. CI `35628587479` was deliberately cancelled before completion once the
new test-only scope was concrete, rather than treated as accepted evidence.
Commit `ae31c731b46bbc677ca64913c3ce2bdf9f62586e` adds 19 substantive cases:
authorized Runtime hits, reindex invalidation/rebuild, replacement between read
and lease, unusable cache envelopes, completed-allocation release with secondary
failures, and corrupt/oversized/foreign POSIX ready receipts with balanced FDs.
It changes only three test files; production Python is byte-identical to
5e4058c3. That earlier freeze required its own complete CI coverage artifact,
which remains under `r5c-contract-ci/`; its browser attempt still failed as
recorded below. Earlier lines or partial browser greens are never merged into
this round's acceptance.

### Retained ae31c731 failed complete browser attempt

| Primary batch | Records | Passed | Failed               | Owned runtime removed |
| ------------- | ------- | ------ | -------------------- | --------------------- |
| retained      | 12      | 12     | None                 | True                  |
| refresh       | 11      | 10     | repeatedFilterIntent | True                  |
| seams         | 7       | 7      | None                 | True                  |
| indexing      | 4       | 4      | None                 | True                  |
| lifecycle     | 1       | 1      | None                 | True                  |
| public        | 2       | 2      | None                 | True                  |

The complete primary matrix ran all 36 original records plus one new download record on `ae31c731b46bbc677ca64913c3ce2bdf9f62586e`: **36/37 passed; 1 failed**. All six owned runtime roots were removed. The failed record was not retried, and the preregistered complete confirmation matrix is **not executed**. This is a failed complete attempt, not a limited verification pass.

Confirmation was preregistered before the transport change. It was not started
after the primary failure. Every failed callback is separately classified using
its existing failure contract or exact owned revoked-Source evidence. Expected
denial is not counted as successful download generation.
No queue settlement, precise-ID, public permission, W1 or W2 guard is weakened.

The original blocker records session `t4uzkb6e5i`: old A request 3
returned at backend call/return/postprocess, another A request 4 applied before
the final A input, B request 5 was rejected, and latest A request 6 was not
validated before the test exited. Its transport/assignment/scheduling stages
were not recorded. The exact original suppressed stage is therefore not
retroactively claimed. `aba-browser-blocker.json` and the original report at
bccae366 retain that failure; the historical 36/37 never becomes a pass.

### B1 causal classification and two separate contracts

The fixture asserted that every old JSON result must reach `applyFiles` before
latest A is released. The actually installed and served Gradio **4.39.0** bundle
`Blocks-BPGBf-rO.js` has SHA-256
`0742ee7d0374cdd5f1b0aa66c562570fb86280f13c86ad02bb9efda5c6e251b1`.
Its source map, actual App dependencies, trigger mode, JS registration,
concurrency configuration and served bytes are retained. No newer-version
documentation or unchanged-file claim substitutes for the causal evidence.

The real frontend permits three observed forms of intermediate-value coalescing:
multiple assignments in one flush; replacement before the deferred change
callback; and an already started callback waiting for pending component updates.
For the third path, a WeakMap in the test observer links the actual local
unsubscribe-function identity to the exact wait/resume invocation. JS reads
current component values after that wait. Each form has a controlled full-App
reproduction with old transport/assignment, positive replacement/dispatch or
wait/resume evidence, and eventual latest application. These controlled probes
are not counted as natural full-matrix cases.

The full-App assertion now requires exact input → captured stamp → backend
fn/event/session/user → SSE transport → hidden JSON assignment → change/JS
scheduling → production guard → all four component values and DOM. Old A must
either be observed and rejected by the actual guard, or have positive coalescing
evidence tied to a separately verified replacement event in the same context.
Missing logs, completion alone and a missing transport do not satisfy it.
The latest legal result must actually commit its four outputs, exact authorized
IDs, Focus and summary. All post-input obsolete applications remain forbidden.

The independent controlled Node layer imports the real production guard. It
forces old and latest arrivals, checks four-output refusal/acceptance, and rejects
foreign mounted context. It is not presented as the natural browser chain.
The original 51 Node cases remain, with 42 new cases: 93/93 in the final source.
Negative controls cover old application, latest completion without application,
missing/failed/partial observers, missing transport/assignment/dispatch,
wrong event/IDs/three outputs, absent component commit, wrong Focus/summary,
cross-user/session/conversation/epoch, unrelated resume and non-pending callbacks.
No golden, xfail/skip, concurrency or trigger-mode change was used to pass.

| Assertion             | Previous fixture                                            | Current contract and evidence                                                                                                        |
| --------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Old A path            | Every old A must enter applyFiles before latest is released | Actual guard rejection OR positively correlated component/dispatch/wait coalescing; no missing-log inference                         |
| Latest A              | Old-observer wait could stop before latest release          | Release and prove exact latest stamp, guard return, four component commits and authorized DOM IDs/Focus/summary                      |
| Forced guard arrivals | Natural delivery was also used as the refusal witness       | Separate real production-guard tests force old rejection and latest acceptance, with invalid-observer/output/context counterexamples |

`b1-causal-classification.json` hashes the retained old blocker and each diagnostic.
The three controlled full-App proofs are `r5c-b1-closeout/b1-controlled-contract/`,
`b1-controlled-deferred/` and `b1-controlled-pending/`; their actual source/observer
inputs and event sequence witnesses are retained separately from final acceptance.

Classification: an over-specific fixture/observation path contract, with legal
framework value coalescing; no production refresh defect was demonstrated.
Both commits are test-only. C1/C2/C3, production guard, W2, L1/I1, writer/ZIP,
restore and completion tails remain unchanged.

All diagnostic failures remain: the initial EventSource probe missed Gradio's
fetch-based SSE; an early flush gate blocked latest submission; the first
contract repair omitted deferred reading; and frozen 43ca5391 omitted the
pending-update wait path. At 43ca5391, retained 12/12 and refresh 10/11 completed:
**22/23 attempted records passed, one failed; other four batches and confirmation
NOT RUN**. This partial failed attempt was retired, not combined with later
greens. CI 35677536809 was cancelled after the concrete observer repair;
its 20 actual jobs and logs remain (11 success, 4 failure, 5 cancelled).
The first Python evidence download there was truncated and failed its digest;
the failed bytes remain, and one separate download matched the exact metadata
digest before inspection. No failed artifact was accepted.

### Final same-source verification

| Batch     | Primary passed | Confirmation passed | Failed | Owned runtime removed |
| --------- | -------------- | ------------------- | ------ | --------------------- |
| retained  | 12             | 12                  | 0 / 0  | True / True           |
| refresh   | 11             | 11                  | 0 / 0  | True / True           |
| seams     | 7              | 7                   | 0 / 0  | True / True           |
| indexing  | 4              | 4                   | 0 / 0  | True / True           |
| lifecycle | 1              | 1                   | 0 / 0  | True / True           |
| public    | 2              | 2                   | 0 / 0  | True / True           |

Both complete matrices passed **37/37** on `41274852f1fda541b3162d5ae39a43beb8e92605` with the identical
source/test/harness. Each used the six original fixture batches, fresh owned
runtime/cache and exclusive port 8768, with serial App startup. No selective
retry or cross-SHA/batch assembly was used. Natural B1 event-level proofs and
four-output/DOM evidence are in each refresh result; all callback failures are
separately classified by the existing denial/fault contracts. Native Windows
capability refusal is not a successful download claim. Browser security smoke
is separately retained and does not replace these full matrices.

| Natural B1 batch | Session       | Old / latest event                                                      | Backend / guard fn | Actual old fate | Latest output                                                     |
| ---------------- | ------------- | ----------------------------------------------------------------------- | ------------------ | --------------- | ----------------------------------------------------------------- |
| primary          | `qg09h3k9yf`  | `ce69bd7598b147389dd00b5227e89562` / `3bc800c05f774a8bbd6fcfa2041ed4d5` | 117 / 116          | guard-rejected  | 4 components; exact r3c-browser-owner-text; Focus/summary matched |
| confirmation     | `c54mwmoghtt` | `4180bc169aee4295988b9557f7391eff` / `efcc6d9a613e4f84bf5c701385a61d22` | 117 / 116          | guard-rejected  | 4 components; exact r3c-browser-owner-text; Focus/summary matched |

`natural-b1-final-proofs.json` retains the exact stamps, final DOM, component IDs,
result hashes and observer health. `source-harness-equivalence.json` verifies all
12 browser input hash maps, all six fixture pairs and the external harness
against the pre-run freeze; no runtime root was reused.

| Gate                                | Actual result                                                                                                 | Qualification                                                                     |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Windows affected full suite         | 99 failed, 4125 passed, 9 skipped, 135 warnings in 558.68s (0:09:18)                                          | Exact retained nodes and failure nature; no new/resolved/changed failures         |
| Windows kotaemon full suite         | 4 failed, 405 passed, 23 skipped, 90 warnings in 151.33s (0:02:31)                                            | Exact retained nodes and failure nature; no new/resolved/changed failures         |
| Unified collection                  | 6324 exact nodes                                                                                              | No added or removed node compared with ae31c731                                   |
| ktem isolated runtime               | 3964 passed, 0 skipped, 140 warnings                                                                          | Full Linux job; warning bodies compared                                           |
| Coverage floors and production diff | 1635 passed, 0 skipped, 8 warnings; 422 passed, 10 skipped, 93 warnings; 3964 passed, 0 skipped, 140 warnings | Full Linux job; warning bodies compared                                           |
| kotaemon Python 3.10                | 422 passed, 10 skipped, 93 warnings                                                                           | Full Linux job; warning bodies compared                                           |
| kotaemon Python 3.11                | 422 passed, 10 skipped, 93 warnings                                                                           | Full Linux job; warning bodies compared                                           |
| Benchmark and root contracts        | 1635 passed, 0 skipped, 8 warnings                                                                            | Full Linux job; warning bodies compared                                           |
| Node                                | 93/93                                                                                                         | Original 51 plus 42 new controlled/negative cases                                 |
| Linux-model mypy                    | 1,972 files passed                                                                                            | Actual Linux static CI also passed                                                |
| Full native Windows mypy            | 15 platform-interface errors in 6 unchanged files                                                             | Broader than the historical 3-error changed-file hook scope; no shim or waiver    |
| Static/hygiene                      | All applicable hooks, Ruff, both ratchets, locks and supply-chain checks passed                               | No baseline/alias/floor/job widening                                              |
| Build/clean-wheel                   | 8 archives and 4 clean installation smokes locally and in CI                                                  | Retained C1/C2/C3 members and generated .pyi verified                             |
| G0/secrets                          | Exact controls and source history scan passed                                                                 | Final report scan and input-equivalence receipts accompany the report-only commit |

Windows failure and warning comparisons remain separate from Linux results.
Linux ktem warnings changed from 139 to 140: the only extra occurrence is the same Gradio version notification at `test_sso_factory_mount_has_login_route_without_model_services`; after removing Actions timestamps and ANSI control sequences, every other warning-summary byte is identical. The log diff and installed background version-check source are recorded in `ktem-warning-occurrence-comparison.json`. No version upgrade is made.
Both kotaemon jobs retain 93 warnings. Their only raw body delta lists the same redundant template keys as `word,language` instead of `language,word`; the existing template code joins an unordered set. The comparison recognizes only those two exact bodies and retains both raw logs, without suppressing other warning changes.
The coverage subprocess also records 139→140 ktem warnings: that same SSO occurrence is added, and one existing background version notification is attributed to a different storage-lifetime test. All other normalized warning-summary bytes are identical (`coverage-warning-occurrence-comparison.json`); no new warning body is hidden by the count comparison.
Full Windows type errors are the same as the retired-source full check; all six files are byte-identical to ae31c731. The local archives retain protected working assets, so full byte equality with CI archives is not claimed.

| Package   | Covered / statements | Percent  | Original floor |
| --------- | -------------------- | -------- | -------------- |
| benchmark | 17146 / 19005        | 90.2184% | 90             |
| slide_cli | 2144 / 2837          | 75.5728% | 70             |
| kotaemon  | 7833 / 11012         | 71.1315% | 60             |
| ktem      | 43696 / 51886        | 84.2154% | 50             |

| Production diff | Base                                       | Covered / total | Percent                    |
| --------------- | ------------------------------------------ | --------------- | -------------------------- |
| fixed_dev       | `adab3f4d8f221e3620494fab0a24ef8e5557d12a` | 2151 / 2235     | 96.2416%                   |
| r5c_increment   | `703eef5fb6e597e049cc49d527d780764730afe4` | 580 / 620       | 93.5484%                   |
| b1_increment    | `bccae366647f0e3fcb4a9df2f48f90827c09ecfb` | 0 / 0           | N/A: no production changes |

Coverage artifact `10675272681`, SHA-256 `97f5348ef9993f91e3f806c04a57a391e83ba3367e41a819ef73cbffa04c993f`. Original collector, subprocess coverage, source aliases and floors are unchanged; missing lines remain in `coverage-verified.json`. High coverage does not substitute for lifecycle contracts.

### Actual CI and security disposition

[Quality Gates run 35678430253](https://github.com/262412/MARA/actions/runs/35678430253) completed on `41274852f1fda541b3162d5ae39a43beb8e92605`: **FAILURE**, **13 success, 7 failure across 20 actual jobs**.

| Job                                                        | Job ID       | Conclusion | Failed step                                     |
| ---------------------------------------------------------- | ------------ | ---------- | ----------------------------------------------- |
| ktem isolated runtime                                      | 106589898411 | success    | None                                            |
| Container ollama supply chain                              | 106589898569 | failure    | Enforce frozen container vulnerability baseline |
| Container lite supply chain                                | 106589898577 | failure    | Enforce frozen container vulnerability baseline |
| Four clean wheel installations                             | 106589898601 | success    | None                                            |
| Coverage floors and production diff                        | 106589898606 | success    | None                                            |
| Frontend and browser security                              | 106589898613 | success    | None                                            |
| Dependency audit root-py311                                | 106589898633 | failure    | Fail on known Python dependency vulnerabilities |
| Python distribution supply chain                           | 106589898641 | success    | None                                            |
| Dependency audit root-py310                                | 106589898646 | failure    | Fail on known Python dependency vulnerabilities |
| kotaemon Python 3.10                                       | 106589898654 | success    | None                                            |
| Static, hygiene, and baseline ratchet                      | 106589898656 | success    | None                                            |
| slide_cli                                                  | 106589898695 | success    | None                                            |
| kotaemon Python 3.11                                       | 106589898716 | success    | None                                            |
| Container full supply chain                                | 106589898718 | failure    | Enforce frozen container vulnerability baseline |
| Unified pytest collection                                  | 106589898752 | success    | None                                            |
| Benchmark and root contracts                               | 106589898758 | success    | None                                            |
| Dependency audit container-py310                           | 106589898770 | failure    | Fail on known Python dependency vulnerabilities |
| Repository and image secret scans / Repository and history | 106589898959 | success    | None                                            |
| Repository and image secret scans / Built image            | 106589899030 | success    | None                                            |
| Required quality gates                                     | 106597807078 | failure    | Require every gate to succeed                   |

| Audit profile   | Blocking keys | New / resolved |
| --------------- | ------------- | -------------- |
| root-py310      | 14            | 0 / 0          |
| root-py311      | 14            | 0 / 0          |
| container-py310 | 14            | 0 / 0          |

| Target | Blocking keys | New raw / blocking | Image digest                                                              | Image SBOM |
| ------ | ------------- | ------------------ | ------------------------------------------------------------------------- | ---------- |
| lite   | 4             | 0 / 0              | `sha256:8f71ff1bb0c9dd42e2d05c59870409524adc2f8439f96bfc51b90461aef5f9d0` | False      |
| full   | 4             | 0 / 0              | `sha256:84ece183d4aa0f4af5d537bece458d9a3011def3b8e52aeea6ce857409577486` | False      |
| ollama | 4             | 0 / 0              | `sha256:17d4770c53b2f797b47e8d79329f671a5141f39f89b452974c2576fb308b4a14` | False      |

Container build/runtime smoke and security failures are classified by exact step. All image startup/runtime smokes passed; the blocking security step prevented image SBOM generation, so no image SBOM is claimed. Python CycloneDX/SPDX/provenance and all eight archives were separately verified. Findings remain blocking: no dependency upgrade, baseline or alias refresh, policy waiver, scan narrowing or required-job change. S1/PCRE2 OPEN; merge/release NO-GO.

One read-only jobs API response was truncated (`ci-progress07-failed-read.json`), and the first coverage-log HTTPS connection failed before creating output (`ci-final-log-first-read-failure.json`). Both retrieval failures are retained. Fresh reads of the missing evidence completed without rerunning CI; final counts use the complete API snapshot and verified job logs.

### Commits, protection and review boundary

| Actual SHA                                 | Change                                                                               |
| ------------------------------------------ | ------------------------------------------------------------------------------------ |
| `eb7f2b8ba5421344241964deca61a79adb91eefa` | test(graph): characterize cache snapshots and reproduce partial publication          |
| `44e678539d7d1d98f1960bc9b7590163300af5a2` | fix(graph): publish complete snapshots and diagnose malformed caches                 |
| `986c9a7c87548ce575e06889d2b8a0d71efeac40` | refactor(graph): share snapshot IO behind existing service seams                     |
| `7499618dc3a5a3a122e37787c93be4f775d69e2a` | test(notebook): reproduce lost updates across independent sessions                   |
| `c4adce39867904756e0a39cd6f242f15e7fee22a` | fix(notebook): coordinate all conversation JSON commit boundaries                    |
| `632d099a09f2bee321c4437040805fa74a4e378d` | refactor(notebook): isolate authorized short transactions from record rules          |
| `134f7d59d125fde4438c5bd3cb7ed69ccf0ee259` | test(graph): reproduce stale publication and missing conversation scope              |
| `ea0d806428dec8fdc074b96536f018a6a9239b49` | fix(graph): reject superseded builds and revalidate source and session scope         |
| `60950beaf5b8013474937e4f9e0b9818e7ade932` | test(graph): reject unauthenticated Runtime cache reads                              |
| `0f32eb86513541c186cad0c94aa5292d5bebcaec` | fix(graph): authorize Runtime cache reads with the current request identity          |
| `5748340e271adb9b761d2ba46ae15ba2a3077fe5` | test(download): reproduce descriptor leaks and unsafe repeated closes                |
| `2505a6cd4e7f0b2858d9daca02fcb96d0f18a64b` | test(download): cover partial allocation and secondary release failures              |
| `023a51b220051af09a745da575f81d19a9160f4b` | fix(download): release partial allocations without masking primary failures          |
| `5842e33500ec0507425c5f6235d5c03a70168f79` | test(download): demonstrate shared HTTP bytes after deletion and revocation          |
| `7d8cd3317b33dc1cced98746edf865a948924edb` | test(download): cover cancellation transfer retention and descriptor reuse           |
| `32cf7455a541ea907f764ce880b8e81bb9ec57c0` | fix(artifacts): close stream duplicates and retire released descriptor numbers       |
| `5a9ef1d4f9d1c52cc8805607bbe4888d8b15c706` | fix(download): authorize HTTP claims and retain resources through transfer           |
| `372acb0f3255b877ee0a7cb5cb17b80fca3442cb` | test(graph): exercise reindex scope changes and visible permission failures          |
| `0530bc862ebd7675eae69aab680a77e9e985a32e` | fix(graph): preserve cache IO permission failures instead of treating them as misses |
| `fd4e90b70dd005606cab7a22a8dd3e8a5b37068c` | test(notebook): verify real storage stages and same-host process coordination        |
| `d5771af18ec5f60b9deb6da1a6b3c38802a059a1` | test(browser): cover scoped download revocation and native capabilities              |
| `553da46d2112b6aedd2aab40de06f682bc315314` | test(download): require the scoped route in the final HTTP fixture                   |
| `205a3bba819bf13d0efc230f89e367e59ea9487f` | test(download): reproduce read-only component import failure                         |
| `33716dda50500ad027210f1decf5aaf6f5e76798` | fix(download): ship Gradio interface for read-only installations                     |
| `5e4058c3f1200627dc609d17f585475ae0dd3a4f` | test(browser): wait for PDF viewer initialization before search                      |
| `ae31c731b46bbc677ca64913c3ce2bdf9f62586e` | test: cover authorized cache reads and completed allocation cleanup                  |

B1 follow-up commits:

| Actual SHA                                 | Change                                                                                          |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| `bccae366647f0e3fcb4a9df2f48f90827c09ecfb` | Prior BLOCKED report and this round baseline                                                    |
| `43ca5391bd730699e8b9d2247e7effe84e6f07e3` | Test-only event/component/guard contract repair; retired partial matrix retained                |
| `41274852f1fda541b3162d5ae39a43beb8e92605` | Test-only exact pending-flush invocation observation and negative controls; final frozen source |

The original 133 user changes plus the two later modified paths remain byte
identical to the initial 135-path inventory. The two later CRLF-only paths can be
absent from normalized `git diff`; raw-byte protection covers both. `NUL` remains
95 bytes with SHA-256 `bd28ac1693f0d94ea97696fed16879a2e2cfeecf19d350451f49224ba1955a3c`.
Canonical environment/known real runtime metadata and the three historically
refused cleanup directories are compared without mutating them. Only task-owned
resources and explicit staged paths are used. The now-required committed `.pyi`
is preserved as package data; its earlier untracked test-generated predecessor
and removal receipt stay in the failed-source evidence.

The first final metadata comparison mixed two collector representations and
failed. The initial command is retained in the task transcript: it hashes sorted
Windows relative paths, size, modification time and mode using non-following
stat. The older standard collector instead uses POSIX relative paths and a
directory flag. Repeating the exact original representation matches every
initial directory fingerprint; the standard representation independently matches
the accepted R5-B final snapshot. Neither failed comparison was a content change
or grounds for replacing the initial fingerprints.

`r5c-b1-final-state.json` records source/test/package, report, local and remote SHAs,
normal-push results, protection hashes and final secret scans. For a report-only
commit, `report-functional-equivalence.json` proves that every other tracked
mode/blob is unchanged before reusing the frozen functional evidence. The entire
previous R5-B report is retained below as historical wording; its then-pending
acceptance is superseded only by the user's explicit acceptance above. The
original R0/R1 historical suffix remains byte-identical.

`r5c-contract-verification/historical-attempt-index.json` hashes every retained local attempt from all
superseded R5-C sources, including failed commands and their original working-input
fingerprints in `execution.jsonl`. Original accepted R5-B double 36/36 evidence
remains under `r5b-browser-closeout/` and `r5b-browser-ci/`.

The current report prefix alone is updated. The entire archived R5-B suffix is byte-identical (SHA-256 `a509b3fcbfc23e5d0fb6d37cb646c405316656cc93ee212a193b3215cebff872`). No new report archive is nested. The final report commit SHA is recorded in the final receipt and ordinary-push receipt; its other tracked modes/blobs and all 135 protected working hashes must match the frozen source.

<details>
<summary>Archived R5-B report at 703eef5f (historical acceptance wording)</summary>

# Safe-refactor status

## Current review point: R5-B browser blocker closeout

Branch: `codex/r0-r1-safe-refactor`. Round baseline/report:
`e8564b6a1ff67d36c2c3afdb68479a58d6aa173a`; preceding stable source/tests:
`ebffe3bf101ece48d2dae1bd19ea691e958cf374`; fixed original Dev:
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`.
R1–R5-A accepted scopes and G0 CLOSED are retained. R5-A acceptance remains
limited to reviewed code/tests/remote-CI evidence, not certification of every
local environment, platform, or security property. R5-B is **not ACCEPTED**.

**R5-B 浏览器阻塞关闭，限定验证通过，等待独立审查。** W1 is an observer
assertion defect established from actual operation/application traces. W2 is a
product event-order defect reproduced with a held close callback and an actual
new selection. Both have separate red/green evidence and commits. The primary
and confirmation complete matrices each pass **36/36 on the same frozen
source/test SHA**, without combining results. Overall CI is **FAILURE**
(13 success, 7 failure); S1/PCRE2 remain **OPEN**, merge/release **NO-GO**.

### Commits and evidence ownership

Frozen source/test tree and last production commit:
**`26e13211963618a5542eacb0f7aee36e59510b16`**. Last dedicated test commit:
`ad6b25239d3ee435a7106e30196b62f741e6f71f`.

| Purpose                                                                         | Commit                                     |
| ------------------------------------------------------------------------------- | ------------------------------------------ |
| Observe owned operation → request → processed input → return → apply/skip → DOM | `2b2458b61be379fa053ad70d06d0ddc16aabc8c0` |
| W1: distinguish legal early A from a stale return; preserve exact final IDs     | `d533a141cfca96c558addaa727f4bb3e67d68606` |
| W2: failing close/selection lifecycle tests before production change            | `ad6b25239d3ee435a7106e30196b62f741e6f71f` |
| W2: close the editor before publishing the next selectable group list           | `26e13211963618a5542eacb0f7aee36e59510b16` |

Only `libs/ktem/ktem/index/file/_events.py` changes in production: the save and
delete chains move their existing close callback ahead of their list refresh,
two lines relocated. The other 13 paths are tests/harness files. There is no
new architecture, global request/state registry, retry, permission fallback,
or dependency change. Existing `.then` behavior, notifications and callback
signatures remain. The original core/adapter and 12-output submission contracts
are preserved.

Evidence root: `D:/PythonProject/MARA-refactor-review-20260910-01a086ff/`.
`r5b-browser-closeout/` holds controlled traces, original assertion stacks,
browser results, local tests/builds and protection receipts. `r5b-browser-ci/`
holds this source's single complete Actions attempt, raw logs and artifacts.
The preceding `r5b-blocker-closeout/` verified/confirmation failures and
`browser-closeout-receipt.json` / `browser-unresolved-diagnostics.json` remain
unchanged. The earlier report is retained at e8564b6a; no failing batch is erased.

### W1: operation identity corrects the observer

The previous complete verified batch failed `repeatedFilterIntent` because it
required the unfiltered three-ID list while the final A was held. The controlled
`observer-targets` reproduction uses unchanged production. Its actual browser
sequence proves that a separate legitimate refresh for the first A applied
before the real B input: request 4/filter-version 1 applied at sequence 13;
B's actual input is sequence 15, and the last A input is sequence 18. The held
first-A request 3 and B response subsequently return with `applied: false`.
The intermediate one-TXT list was therefore legal. A test action label alone
was insufficient because it was assigned before the corresponding input event.

The repaired observer identifies first and last A by actual event ID, function
ID, filter version and request stamp. It requires the old held A to reach the
real apply boundary and be rejected, rejects every obsolete applied filter
after the last input, then requires the exact latest request to apply all four
outputs. Exact final file IDs and the Focus/summary DOM values are checked
against the actual applied payload. It does not substitute request termination
or an unchanged filter string for successful UI application.

`file_browser_refresh.js`, `file_browser_updates.py`, authenticated source
queries and existing epoch/filter/view/catalog/request guards are unchanged.
`w1-controlled-green` covers initialization overlap, busy intent, reverse
completion, A→B→A and browser/user isolation. The full matrices retain catalog
notifications, URL/upload/delete side effects and conversation/source switches.
Node counterexamples reject a stale first A, a completed-but-unapplied latest A,
and a three-slot result. No persistent selection rule or precise-ID assertion
is weakened. Classification: **test observer defect; no W1 production fix**.

### W2: prevent an older close from erasing a new selection

`w2-selection-red` holds the existing save-tail close callback after the old
chain has exposed the refreshed group list. A real browser row click invokes
`interact_group_list`; server postprocessing installs the exact stable group
UUID. Releasing the older close then writes `selected_group_id = None`.
`root-causes.json` retains that ordered identity/selection/close proof, including
list-version hashes. The preceding complete confirmation's later
`GroupServiceError: No group found` is no longer attributed to a guessed cause.

The minimum product change is **save/delete → close → list → existing index
notifications**, instead of save/delete → list → close. A fresh selectable list
is not exposed while its older close remains pending. The controlled green
keeps the same close barrier and proves the new row is unavailable until close
has applied; its subsequent natural click installs the stable UUID, and the
authenticated `set_group_id_selector` receives that UUID and returns the
original three outputs. The actual Chat interface and subsequent flow complete.

The harness retains the counterfactual quick-click branch that fails on the old
product. It records the real preprocessed inputs, trusted fixture request user,
function/event/session identity, raw return and postprocessed selection. Owner
checks, original group encoding and service queries are unchanged; no selection
is guessed from a name or default first row. Missing/foreign groups still fail.
`GroupServiceError` is not added to a passing failure allowlist. Classification:
**product event ordering defect**, not an infrastructure timeout.

`w2-lifecycle-red` fails both save/delete ordering cases before the fix;
`w2-targeted-green` passes 31 tests, and frozen-source permission regressions
pass 17. `red-green-source-receipt.json` binds red runs to unchanged production.
Early greens record their actual working patch hash; the later mixed-line-ending
hook and its passing rerun are retained separately. Both final complete matrices
and all delivery gates use the committed, normalized 26e13211 tree.

### Two complete browser matrices and completion criteria

Each attempt uses fresh empty runtime/cache state, serial fixtures and exclusive
port 8768, including the separate public fixture. The unchanged full App,
Gradio 4.39 registration, real upload/indexing, authentication and persistence
remain under test. Deterministic model/network boundaries are retained. No
manual middle API, cache warmup, force click, repeated click or global sleep/
network-idle substitute is used. Task-only observers/barriers expose no new
production debug endpoint and contain only owned fake-user fixtures.

| Fixture batch     | Main acceptance | Confirmation | Retained scope                                                                                                                  |
| ----------------- | --------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `retained`        | 12/12           | 12/12        | Two-turn stream/citations/cache/naming/persist/reload; empty/new/delete/switch; upload/URL; error/disconnect; navigation/search |
| `refresh`         | 11/11           | 11/11        | Initialization, reverse and A→B→A; catalog/selector/source/conversation changes; two browsers/users                             |
| `seams`           | 7/7             | 7/7          | Real index manager and Group→Chat; revoked preview; Studio note/source/artifact/switch/error/disconnect                         |
| `indexing`        | 4/4             | 4/4          | Real ZIP success/writer failure and disconnect; delete/replacement/late writer; two-owner cache and survivor citations          |
| `public`          | 2/2             | 2/2          | Public read plus nonowner mutation/Studio denial                                                                                |
| **Whole attempt** | **36/36**       | **36/36**    | **Same source/test SHA; no cross-batch or cross-SHA green assembly**                                                            |

`two-complete-matrices.json` records every result hash, source and successful
owned-root cleanup. The original 36-record scope is retained. Main diagnostic
verification completed before starting confirmation. Both strict diagnostic
receipts pass. Expected failed requests are not counted as successful features:
intentional generation/error tests assert their failure behavior; nonadmin
listing denial remains separately identified. The confirmation's two rejected
`file_selected_2` requests are each tied to the exact deleted Source, same-session
delete and following clear tail. They prove preview revocation, not a new blanket
failure exception. Full assertion/error stacks remain outside Playwright tracing,
which does not automatically capture `expect` calls in this script harness.

`settled()` remains unchanged. The two repaired flows now wait for their specific
application endpoints: latest four-output filter application and stable-ID group
selection/query plus Chat DOM. The concurrency barriers remain active. The prior
two 35/36 attempts at ebffe3bf stay failed; they are not combined with this source.

### Retained lifecycle and public contracts

`frozen-scope-protection.json` verifies unchanged L1/I1 production, writer/iterator/
ZIP ownership, group authorization, filter guards, locks, security policies and
coverage gates. The full Linux suites and both browser matrices re-exercise the
accepted safety seams: Source-level cross-object/process exclusion, fresh delete
planning, delete/recreate/late-write refusal, independent persistent IDs with
shared parser cache, writer failure/cancellation and owned ZIP cleanup.

L1 retains Source lease → optional content lease → short SQL ordering, with worker
join outside the Source lease. I1 retains copied Source/table-namespaced persistent
IDs without mutating borrowed cache objects. These fixes do not migrate historical
collisions or restore already-corrupted data. SQL rollback still cannot restore
deleted external indexes. Uninterruptible I/O, separate-root/multi-host fencing,
unexecuted desktop binaries and other untested platform artifacts are not certified.
The current round does not expand those claims or modify the prior safety repairs.

### Complete suites, static checks and actual artifacts

| Gate at frozen source/test tree | Actual result                                                                                                                                     |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Windows full affected suite     | 4,022 passed, 99 failed, 9 existing skips; no new/resolved failure nodes or changed primary error/assertion nature                                |
| Windows kotaemon suite          | 389 passed, 4 failed, 15 existing skips; the same four FIFO/symlink-capability failures, separately compared                                      |
| Linux ktem isolated suite       | 3,861 passed, 108 warnings                                                                                                                        |
| Linux benchmark/root suite      | 1,635 passed, 8 warnings                                                                                                                          |
| Linux kotaemon Python 3.10/3.11 | 398 passed, 10 existing skips on each version                                                                                                     |
| Unified collection              | 6,197 nodes; all 6,193 preceding nodes retained, 4 added, none removed                                                                            |
| Node                            | 51 passed, zero failed/skipped; actual production JS and observer counterexamples                                                                 |
| Static/hygiene                  | Explicit round hooks, repository Ruff, 1,947-file Linux-model mypy, full/incremental/fixed-Dev ratchets, lock parity and supply-chain policy pass |
| Local build                     | Four wheels and four sdists; metadata and changed production member hashes verified                                                               |
| Outside-repository clean-wheel  | All four installed packages pass real exports/CLI/resource and retained lifecycle/application smokes                                              |
| Fresh CI artifacts              | Python metadata/provenance and CycloneDX/SPDX verified; four clean-wheel installations pass; image SBOM status is reported separately below       |

Windows tests use the isolated task environment, never a canonical sync. Local
Linux-model mypy is distinguished from the actual Linux CI execution. The existing
99 failures are compared by node, main error and assertion nature in
`delivery-affected-suite-comparison.json`; the four kotaemon failures have their
own comparison. No new skip/omit or baseline refresh was introduced.

`delivery-local-diagnostics.json` retains one raw warning-text difference:
`word,language` versus `language,word`. Unchanged template code joins a set;
both exact forms and unchanged source/test hashes are recorded. There is no new
unexplained local warning, unhandled-thread warning or unraisable exception.
Current/prior CI warning bodies, suite totals and exact collection node deltas
are in `r5b-browser-ci/test-evidence-comparison.json`; image warnings are compared
separately. No new issue is labelled NLTK or folded into the old 99 by count alone.
The coverage invocation reports 107 ktem warnings versus the preceding 108;
its complete warning bodies add nothing new. Existing out-of-summary coverage
warnings and Actions annotation warnings are also compared without a new waiver.

Local archives: `D:/MARA-s1-01a086ff/r5b-browser-final-dist`, verified by
`delivery-local-build-verified.json`. CI Python artifact `10643073726`, ZIP SHA-256
`f21d0266cd2935d6c9f4231212c57b5372c7fc48fc9124e329a79e1600ab90e0`, contains all
eight actual archives and provenance. `python-artifact-inspection.json` verifies
the changed event source and retained L1/I1 members. Local archives retain the
user's asset edits; they are not claimed byte-identical to clean-Git CI archives.

### Unchanged coverage gates

The final-source CI coverage artifact uses the existing collector, subprocess
measurement, package floors and production-diff gate. There are no temporary
runtime files or package-relative aliases substituted for production sources.

| Package   | Covered / total | Percentage | Original floor |
| --------- | --------------- | ---------- | -------------- |
| benchmark | 17146 / 19005   | 90.2184%   | 90%            |
| slide_cli | 2144 / 2837     | 75.5728%   | 70%            |
| kotaemon  | 7675 / 10852    | 70.7243%   | 60%            |
| ktem      | 43364 / 51589   | 84.0567%   | 50%            |

| Production diff            | Base       | Covered / total | Percentage                      | Floor |
| -------------------------- | ---------- | --------------- | ------------------------------- | ----- |
| fixed_dev                  | `adab3f4d` | 1571 / 1615     | 97.2755%                        | 90%   |
| browser_closeout_increment | `e8564b6a` | 0 / 0           | No executable diff (gate: 100%) | 90%   |

The incremental 0/0 is the existing collector's treatment of two relocated
continuation clauses in already measured chained statements. It is not a claim
that new runtime behavior has 100% independent line coverage: fixed event-order
assertions and the two full browser matrices provide that behavioral evidence.

| Changed event / retained boundary                    | Covered / statements | Coverage  |
| ---------------------------------------------------- | -------------------- | --------- |
| `libs/ktem/ktem/index/file/_events.py`               | 50 / 51              | 98.0392%  |
| `libs/ktem/ktem/index/file/source_writes.py`         | 73 / 73              | 100.0000% |
| `libs/ktem/ktem/index/file/index_materialization.py` | 41 / 41              | 100.0000% |

Artifact `10646270671`, SHA-256 `5e23bd0f6f2dced440ce4bedb127b57cde756a10c2ca88867a838cf77c041f03` is source/digest verified in `coverage-verified.json`.
Prior accepted boundary modules remain in package scope. Coverage supplements
the complete browser and lifecycle evidence; it does not replace them.
The two fewer covered ktem lines are unchanged `cache_attestation.py:184–185`,
the `FileExistsError`/`pass` branch around atomic key linking, not hit by this
invocation. `coverage-details.json` records the exact source/hash and line delta;
no retry, source edit or omit was used to improve this number.

### Actual single-source CI

Run [35609107410](https://github.com/262412/MARA/actions/runs/35609107410), attempt 1,
source `26e13211963618a5542eacb0f7aee36e59510b16`:
**FAILURE, 13 success, 7 failure**. Every required non-security job passes.
This is one full fresh-source attempt, not a targeted rerun or assembled old jobs.
Every downloaded job log has a source-bound digest receipt.
The required aggregate fails because its dependency-audit and container inputs
fail; its other required inputs report success.

| Job                                                        | Job ID         | Actual conclusion |
| ---------------------------------------------------------- | -------------- | ----------------- |
| ktem isolated runtime                                      | `106363485313` | success           |
| Unified pytest collection                                  | `106363485533` | success           |
| Python distribution supply chain                           | `106363485719` | success           |
| Dependency audit root-py310                                | `106363485739` | failure           |
| kotaemon Python 3.11                                       | `106363485756` | success           |
| Four clean wheel installations                             | `106363485815` | success           |
| Coverage floors and production diff                        | `106363485867` | success           |
| Static, hygiene, and baseline ratchet                      | `106363485888` | success           |
| slide_cli                                                  | `106363485902` | success           |
| kotaemon Python 3.10                                       | `106363485907` | success           |
| Dependency audit container-py310                           | `106363485922` | failure           |
| Dependency audit root-py311                                | `106363485932` | failure           |
| Benchmark and root contracts                               | `106363485937` | success           |
| Frontend and browser security                              | `106363486079` | success           |
| Container full supply chain                                | `106363486125` | failure           |
| Repository and image secret scans / Built image            | `106363486173` | success           |
| Repository and image secret scans / Repository and history | `106363486238` | success           |
| Container lite supply chain                                | `106363486359` | failure           |
| Container ollama supply chain                              | `106363486392` | failure           |
| Required quality gates                                     | `106382754249` | failure           |

### Fresh security results and retained blockers

G0 remains CLOSED: the pinned v8.24.3 exact rule-local exception and ten positive/
negative controls pass unchanged. S1/PCRE2 remain **OPEN**. All three fresh
profiles (`root-py310`, `root-py311`, `container-py310`) retain the same 14 blocking
keys; `security-key-reconciliation-final.json` records exact profile/job/package/
version/ID comparisons and unchanged baseline/alias/lock/workflow inputs.

| Package/version in each profile | Blocking ID(s)                                                             |
| ------------------------------- | -------------------------------------------------------------------------- |
| nltk 3.10.3                     | GHSA-8mgp-746c-j5xp                                                        |
| chromadb 0.5.16                 | PYSEC-2026-3813, PYSEC-2026-3814, PYSEC-2026-3815                          |
| pypdf 4.2.0                     | PYSEC-2026-3910, PYSEC-2026-3911, PYSEC-2026-3912, PYSEC-2026-3913         |
| transformers 4.56.2             | PYSEC-2026-3929                                                            |
| unstructured 0.15.14            | PYSEC-2026-3930                                                            |
| soupsieve 2.8                   | GHSA-gjv8-xp57-g29c / CVE-2026-86000; GHSA-j934-xhv5-fg8f / CVE-2026-85999 |
| anyio 4.11.0                    | GHSA-5p39-cfhj-2xmp / CVE-2026-64847; GHSA-82r6-8w77-94w6 / CVE-2026-63374 |

Each freshly built image retains AnyIO 4.11.0 CVE-2026-63374 and
`libpcre2-8-0==10.42-1` CVE-2026-86145, CVE-2026-89161 and CVE-2026-89157.
Source-bound provenance and raw Trivy 0.70.0 reports are verified; blocking and
raw finding deltas against the preceding ebffe3bf scan are empty. These findings
remain blocking relative to the unchanged security baseline. The old image
baseline's resolved NLTK 3.10.0 entries do not close current-profile NLTK 3.10.3.

| Image  | Artifact ID   | Verified OCI manifest digest                                              |
| ------ | ------------- | ------------------------------------------------------------------------- |
| lite   | `10644135563` | `sha256:c90589a96f5e31c86db52f8b9f9446d3b7ddebb73a768bbc96b9fa839ec46adf` |
| full   | `10644006063` | `sha256:0e618b8f3b270a693d736e5b1091f6c4ec4ebfa8ecff20ee7eefe00e9fd9343a` |
| ollama | `10643779123` | `sha256:fcb706873b8915fda087b29f95f3e5166d943dd174c947eb0ad0678ea613f456` |

Image SBOM export/baseline steps after the failed vulnerability gate are **skipped,
not complete**. Python-distribution SBOM success does not stand in for them.
G0 closure and this functional closeout do not certify security. No lock, alias,
vulnerability baseline, scanner scope, required job or coverage threshold changes.

### Protection receipt and independent review point

All 133 pre-existing asset/instruction modifications remain byte-identical and
unstaged; later edits are not replaced. `NUL` retains 95 bytes and SHA-256
`bd28ac1693f0d94ea97696fed16879a2e2cfeecf19d350451f49224ba1955a3c`.
Canonical `.venv` metadata (98,853 entries), real theflow cache (614 entries),
Office cache and real configuration/database size/mtime records match the initial
snapshot. These are metadata checks, not claimed full-byte database hashing.
All three historical refused-cleanup directories remain. Only task-owned browser
roots are removed after their own producer/server exits; all ten final fixture
cleanup receipts pass.

Only explicitly named files and this existing report are staged. No branch or
worktree is created; pushes are ordinary fast-forward pushes. There is no force
push, migration, full-cache deletion, merge, deployment, release or security upgrade.
The original report suffix remains byte-identical with 853 line breaks.

`r5b-browser-closeout/r5b-report-commit.json`, `report-functional-equivalence.json`
and `r5b-final-state.json` bind actual source/test/report/local/remote SHAs, report
content, final protected snapshots and push verification. The report commit only
changes this document, verified against every other tracked blob before reusing
26e13211 functional evidence. The report itself receives final pinned Gitleaks
worktree and full-history scans; report equivalence does not waive those checks.
`report-artifact-scope.json` confirms that none of the eight Python archives
contains this report. Image provenance remains explicitly bound to 26e13211;
no byte-identity claim is made for an unbuilt image at the later report commit.

**Stopping point: R5-B browser blockers closed in the limited verified scope,
awaiting independent review; R5-B is not ACCEPTED.** Overall CI remains
FAILURE; S1/PCRE2 OPEN and merge/release NO-GO are separate outcomes.
Work stops here without R5-C, R6 or reopening earlier accepted phases.

</details>

## Previous R0/R1 evidence (retained history)

The following sections retain earlier implementation, CI and incident evidence.
Their historical authorization and failure statements do not replace the current
R2-C status above.

### Changes and affected surfaces

The affected surfaces are startup resource/config selection, test-owned
filesystem/storage lifecycle, shared file selection imports and CI coverage
artifacts. Public CLI names and options, database formats,
DocQA routing, prompts, UI event chains and production deadline budgets are
unchanged. The earlier deadline/cancellation fixes remain in history.

- `6eab0f90`: treat `NLTK_DATA` as an ordered search list. Ordinary startup does
  not prepare resource directories; test mode validates every nonempty entry
  and prepares only its first owned directory. Empty test lists select the
  owned cache. Configuration discovery and explicit loading validate the
  resolved file before reading/executing it, then validate returned storage/DB
  paths. Owned module names resolve without executing unchecked parent
  packages. A small initial settings bridge lets TheFlow validate the actual
  custom settings before creating its global storage instance.
- `857d70d0`: validate session ownership before accepting pytest basetemp.
  Reject the session root, aliases, outside directories and overlap with
  config/cache/data/output/temp state. Tests invoke pytest's real basetemp
  clearing and verify the owner marker and state sentinels survive.
- `ea406f8e`: the fixtures that create Chroma stores also stop their owned
  Chroma systems before session cleanup. They remove only matching owned
  registry entries. Tests delete the released native-index directory and
  continue writing through another live instance. A fresh pytest child must
  return zero and remove its session directory after unconfigure.
- `0b8f18c7`: give app-init hardening fixtures their own complete runtime and
  seed the config directory actually used by the CLI. The old fixture inherited
  the parent test root while checking a different config directory.
- `331f9c8e`: read the Windows-specific error code with `getattr` in the two
  new symlink test helpers. The intermediate Ubuntu static job exposed that
  Linux mypy does not define `OSError.winerror`; this is a test portability
  correction and does not weaken the native symlink assertions.
- `cd12795d`: exclude pytest-owned `session-*` fixtures from coverage collection
  and exports under the configured runtime parent (or the existing default).
  A deleted test `flowsettings.py` had the same module name as a root production
  file, so XML export attempted to read it after successful session cleanup.
  Synthetic-data regressions reproduce the original export error, retain all
  four production packages and four root files in XML/JSON, retain uncovered
  statements, and still fail if real production source is missing. No coverage
  collector is started by these local export regressions.
- `8cc9e940`: merge package-relative subprocess coverage paths into their
  canonical repository files before reporting. Six independent cases cover
  all three library packages and both slash styles; they require measurements
  from both paths to survive, one missing line to remain missing, and valid
  XML/JSON. The existing artifact upload now retains hidden coverage data for
  diagnosis. Tests finalize their own Coverage instance, including mapped
  SQLite copies retained internally by its reporting API.
- `26d8e873`: commit 140 fixed-expectation characterization cases before moving
  either production function. Both old import paths, class static methods,
  actual patch consumers, graph composition and DocQA artifact scope are tested.
- `c693160e`: move only `normalize_selected_file_ids` and
  `merge_unique_file_ids` into `ktem_contracts/file_selection.py`. Both old
  modules bind those same function objects under the existing names; all other
  selection/UI logic and the class wrappers remain unchanged. Include
  `ktem_contracts` in the existing ktem coverage floor and production diff gate,
  and verify the new module in built wheels/sdists and clean wheel smoke imports.

The before-fix independent boundary run failed 20 cases. Separate regressions
also reproduced the app fixture mismatch and rejection of an owned benchmark
module name. The real Chroma child previously passed its assertion but exited
nonzero during cleanup with a locked HNSW file. All original assertions were
retained. During repair, a real custom-storage check caught an intermediate
initialization-order error; the final bridge preserves agreement between the
selected settings and the actual storage instance, including a fresh child.

### Local evidence for the pushed source

Evidence is retained outside Git under
`D:\PythonProject\MARA-refactor-review-20260910-01a086ff\next-round`.
`execution.jsonl` records commands, source hashes, cwd, timestamps and exit
codes; failed attempts remain separate from final results.

| Check                                                                                                  | Result                                                                               | Evidence                              |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ | ------------------------------------- |
| Combined boundary, real subprocess, cleanup, Chroma, app-init, deadline/cancellation and CLI contracts | Exit 0; 139 passed, 10 symlink skips, 2 app-init symlink cases deselected for Ubuntu | `final-focused-runtime-lifecycle.log` |
| Changed Python pre-commit, including mypy                                                              | Exit 0                                                                               | `precommit-final-code-pass.log`       |
| Full Ruff and hygiene                                                                                  | Exit 0                                                                               | `final-ruff.log`, `final-hygiene.log` |
| Hygiene baseline against exact original Dev                                                            | Exit 0; baseline not widened                                                         | `final-baseline.log`                  |
| Normal push                                                                                            | `7496c6ae..0b8f18c7`; remote SHA verified                                            | `push-0b8f18c7.log`                   |

The 02:49 UTC snapshot preceded this round's tests. At 07:27 UTC, after the R1
local tests, artifact checks and report verification, the canonical
environment still had the same 98,823 entries and identical metadata hash;
the retained user cache had the same 614 entries and identical metadata hash.
Known profile config/SQLite and repository SQLite size/mtime records are also
identical. See `preserved-before.json` and `preserved-final.json`.
The final 19-test coverage regression run exits zero and removes its own runtime
directory. Two directories from earlier failed synthetic-data tests remain:
`D:\MARA-next-pytest-01a086ff\session-_tt6h466` and
`D:\MARA-next-pytest-01a086ff\session-n97o375r`. Those attempts exposed retained
SQLite handles before the instance cleanup was fixed. Automatic approval
rejected the subsequent recursive cleanup command with `blocked by policy`.
A narrower plan enumerated and hashed 80 regular files (587,882 bytes) and 98
directories, checked that no reparse points existed, and proposed deleting only
those files followed by nonrecursive deletion of empty directories. Automatic
approval rejected that plan too with the same reason; neither cleanup command
ran. No further deletion was attempted. The exact remaining files are recorded
in `runtime-inventory-after-coverage-paths.json` and
`owned-coverage-orphans-manifest.json`.
The post-R1 read-only inventory in `runtime-inventory-after-r1.json` confirms
only those two older directories remain. No `subcover*.pth` files exist.
These are metadata comparisons, not a recovery of the original pre-incident
configuration. The historical real-user configuration/cache incidents and
after-event copies documented below remain part of the record.

No local full coverage was rerun. Subprocess coverage remains enabled in the
Ubuntu workflow, and all four package floors plus the 90% production
diff floor remain required. No dependency or audit/hygiene baseline was changed.

### Ubuntu evidence and R1 decision

The review input `7496c6ae5b7823174cff3e7cc9ea318c0a841fb0` had no existing
Quality gates run, so it was dispatched once with the explicit branch/base.
[Run 34430620710, attempt 1](https://github.com/262412/MARA/actions/runs/34430620710)
completed with **failure** at that exact SHA. Its ktem suite passed 2,644 tests;
both kotaemon versions failed the one config-symlink fixture assertion. Root/
benchmark and coverage each failed four benchmark runtime module-selection
cases. The failures were read before applying the targeted repairs above.

All three dependency profiles rejected nine NLTK 3.10.0 advisory IDs, and all
three container profiles rejected seven NLTK CVE findings. Raw job logs and
the complete job/run JSON are retained as `ci-34430620710-job-*.log` and
`quality-34430620710-*.json`; exact IDs remain in those logs. These are the
scanner findings from the actual run, not a separate exploitability assessment.
Upgrading dependencies or suppressing findings is not authorized in this round.

The intermediate run `34432962143`, attempt 1, tested
`0b8f18c7175c23d3aac23ee9fa621561f1ba86aa`. Both kotaemon versions passed
371 tests / 10 optional dependency skips, including the real config symlink
tests. Static analysis failed only on the two new `OSError.winerror` accesses.
The portable correction passed Linux-targeted mypy using the existing cached
hook environment and the local 33-test boundary suite (10 native symlink
skips). See `portable-symlink-cached-mypy-linux.log`,
`portable-symlink-precommit.log`, `portable-symlink-regressions.log` and
`push-portable-symlinks.log`. The push succeeded; its first follow-up direct
remote query timed out. A read-only query through the existing proxy verified
the new remote SHA without changing Git configuration.

Run `34433661997`, attempt 1, tested `331f9c8ef67012653be81fd2d7daad75288912eb`;
`dispatch-331f9c8e.json` and `quality-runs-331f9c8e-started.json` record dispatch
and run identity. The existing workflow concurrency policy replaced the
intermediate run, whose final conclusion is **cancelled**; unfinished gates
from that run are not counted as passes.
It completed with **failure**. The completed jobs at that revision have these
results; they are not presented as the subsequent source's completed CI:

| Ubuntu check at `331f9c8e`                                                                                        | Result                                                                                               |
| ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Static hooks, full Ruff, hygiene and baseline ratchet                                                             | Passed; comparison uses the exact original Dev SHA                                                   |
| kotaemon Python 3.10 and 3.11                                                                                     | Each passed 371 tests, with 10 optional dependency skips                                             |
| ktem                                                                                                              | 2,644 passed                                                                                         |
| benchmark and root contracts                                                                                      | 1,609 passed, including the four previously failing module-selection contracts                       |
| slide_cli                                                                                                         | Passed; 131 passing progress markers in the successful job                                           |
| Unified collection                                                                                                | Passed; 4,927 tests collected                                                                        |
| Four clean wheel installations, frontend/browser security, Python distribution supply chain and both secret scans | Passed                                                                                               |
| Three dependency audit profiles                                                                                   | Failed: nine NLTK 3.10.0 GHSA findings per profile                                                   |
| Three container profiles                                                                                          | Build/runtime smoke completed; audit failed on seven NLTK CVE findings per profile                   |
| Package coverage floors                                                                                           | All passed: benchmark 90.22% / 90%; slide_cli 75.57% / 70%; kotaemon 70.11% / 60%; ktem 80.89% / 50% |
| Coverage XML/JSON export and production diff                                                                      | XML export failed on removed test settings; JSON and the 90% production diff gate did not run        |

The raw logs for that source use `ci-34433661997-job-*.log`; job snapshots
use `quality-34433661997-jobs-*.json`.
`dependency-audit-findings-331f9c8e.json` retains all nine GHSA and seven CVE
IDs, their exact log lines and the six affected jobs. The two scanner ID
namespaces are not added together as a distinct vulnerability count.
The coverage-instrumented test suites also passed before export: root/benchmark
1,609; kotaemon 371 plus 10 skips; ktem 2,644; and slide_cli's complete passing
progress output. The failure was `No source for code` for a removed test-session
`flowsettings.py`, not a package threshold violation. The uploaded coverage
artifact `10136434812` is only 336 bytes. Downloading and inspecting the ZIP
confirmed that it contains only `coverage.ini`; upload success is not accepted
as valid XML/JSON output. See
`coverage-export-failure-331f9c8e.json` and job `102734405186`'s raw log.

The targeted export repair was committed and pushed as `cd12795d`. Its 13 local
quality-script tests pass, using synthetic data without starting a coverage
collector or installing `.pth` files. Changed-file hooks, the exact existing CI
Ruff command, hygiene and the original-Dev baseline comparison also pass. The
first broader Ruff invocation omitted the workflow's pre-existing exclusions
and reported two existing `.pyi` issues; those files and exclusions were not
changed. See `coverage-export-tests-verified.log`,
`coverage-export-hooks-verified.log`, `coverage-export-ci-ruff.log`,
`coverage-export-hygiene.log`, `coverage-export-baseline.log` and
`push-cd12795d.json`.

[Run 34437287461, attempt 1](https://github.com/262412/MARA/actions/runs/34437287461)
tested exact head `cd12795debafac148f7e7b230e30ad3c6f0b22ec`.
It was dispatched once after checking that this new SHA had no existing run,
using the same explicit branch and original Dev `base_ref`. It completed with
**failure**; these are its final results, not results for the later path fix:

| Ubuntu check at `cd12795d`                                                                                        | Result                                                                                               |
| ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Static hooks, full CI Ruff, hygiene and original-Dev baseline comparison                                          | Passed                                                                                               |
| kotaemon Python 3.10 and 3.11                                                                                     | Each passed 371 tests, with 10 optional dependency skips                                             |
| ktem                                                                                                              | 2,644 passed                                                                                         |
| benchmark and root contracts                                                                                      | 1,611 passed                                                                                         |
| slide_cli                                                                                                         | Passed                                                                                               |
| Unified collection                                                                                                | Passed; 4,929 tests collected                                                                        |
| Four clean wheel installations, frontend/browser security, Python distribution supply chain and both secret scans | Passed                                                                                               |
| Three dependency audit profiles                                                                                   | Failed: nine NLTK 3.10.0 GHSA findings per profile                                                   |
| Three container audit profiles                                                                                    | Failed: seven NLTK CVE findings per profile                                                          |
| Package coverage floors                                                                                           | All passed: benchmark 90.22% / 90%; slide_cli 75.57% / 70%; kotaemon 70.11% / 60%; ktem 80.89% / 50% |
| XML/JSON and production diff                                                                                      | XML failed on `kotaemon/__init__.py`; JSON and diff did not run                                      |

No dependency or audit baseline was changed. `dependency-audit-findings-cd12795d.json`
records the exact findings and raw log lines for all six audit jobs at that SHA.
Raw logs and final snapshots use `ci-34437287461-job-*.log` and
`quality-34437287461-*.json`. All instrumented suites passed before export:
root/benchmark 1,611; kotaemon 371 plus 10 skips; ktem 2,644; slide_cli passed.
The path error came from package-directory subprocess measurements, and the
downloaded artifact `10137660368` again contained only `coverage.ini`. Its SHA256
matches GitHub's artifact digest; see `coverage-artifact-cd12795d-inspection.json`.

The path-mapping correction passed `coverage-paths-tests-verified.log` (19 tests,
exit zero including unconfigure), `coverage-paths-hooks-verified.log`,
`coverage-paths-ci-ruff.log`, `coverage-paths-hygiene.log` and
`coverage-paths-baseline.log`. Its before-fix six-case failure and intermediate
cleanup failures remain in the evidence directory; see
`command-remediation-coverage-paths.json`. Normal push of `8cc9e940` is verified
in `push-8cc9e940-normalized.json`.

[Run 34440810480, attempt 1](https://github.com/262412/MARA/actions/runs/34440810480)
validated `8cc9e9403b92f87b15db82b000c24c65c47b84db`. A query found no
existing run for that SHA before dispatch; the explicit branch and original Dev
base are recorded in `dispatch-8cc9e940.json`. Its final overall result is failure.

| Ubuntu check at `8cc9e940`                                                                                             | Result                                                                                               |
| ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Static hooks, full CI Ruff, hygiene and original-Dev baseline comparison                                               | Passed                                                                                               |
| kotaemon Python 3.10 and 3.11                                                                                          | Each passed 371 tests, with 10 optional dependency skips                                             |
| ktem                                                                                                                   | 2,644 passed                                                                                         |
| benchmark and root contracts                                                                                           | 1,617 passed                                                                                         |
| slide_cli                                                                                                              | Passed                                                                                               |
| Unified collection                                                                                                     | Passed; 4,935 tests collected                                                                        |
| Four clean wheel installations, frontend/browser security, Python distribution supply chain and repository secret scan | Passed                                                                                               |
| Three dependency audit profiles                                                                                        | Failed: nine NLTK 3.10.0 GHSA findings per profile                                                   |
| Three container audit profiles                                                                                         | Build and runtime smoke passed; seven NLTK CVE findings per profile                                  |
| Built-image secret scan                                                                                                | Incomplete: Trivy reached its deadline after approximately five minutes                              |
| Coverage floors                                                                                                        | All passed: benchmark 90.22% / 90%; slide_cli 75.57% / 70%; kotaemon 70.11% / 60%; ktem 80.89% / 50% |
| XML/JSON and production diff                                                                                           | Passed; production diff 93.90% (154/164 statements)                                                  |

All completed jobs' raw logs are retained as `ci-34440810480-job-*.log`, plus
`ci-34440810480-aggregate.log`.
`dependency-audit-findings-8cc9e940.json` records the six NLTK audit failures.
The image secret job built the image successfully, then failed inside Trivy
while acquiring its analysis semaphore (`context deadline exceeded`). It did
not produce a completed secret-scan verdict; this is neither a clean scan nor
a secret-detection finding. See `image-secret-scan-timeout-8cc9e940.json` and
job `102755280292`'s complete log. No scanner timeout, scope or failure policy
was changed, and no unchanged-source rerun was dispatched.

Coverage artifact `10138960793` was downloaded and its SHA256 matched the GitHub
digest. It contains `.coverage`, `coverage.ini`, valid XML and valid JSON. The
996 raw file records have no remaining package-relative aliases, and no removed
test-runtime files appear in the JSON. Artifact-derived package totals match the
job log. See `coverage-artifact-8cc9e940/inspection.json` and
`quality-34440810480-final.json` / `quality-34440810480-jobs-final.json`.

The user-listed isolation, lifecycle, current full-suite, static and coverage
conditions for R1 are now verified at `8cc9e940`. R1 began with 140 fixed-expectation
tests against the untouched old implementations, including the two module
paths, both classes' static methods, real patch consumers and graph/DocQA
callers. That run exited zero, including unconfigure; see
`r1-characterization-old-implementation.log` and the formatted, committed
`r1-characterization-old-verified.log`. No R1 production change preceded those
passing old-implementation tests.

### R1 implementation and current-source validation

The extraction retains duplicates, whitespace, zero/False, tuple conversion,
ordering and exception propagation. Old module imports expose the shared
function objects with their original signatures; existing static methods and
their real module-global patch lookups are unchanged. The two selector
extraction implementations, UI selector, `chat_submit_sources`, routes,
prompts and persisted representations are unchanged. `r1-ast-equivalence.log`
compares the two shared function ASTs against both originals at `8cc9e940`,
checks all other top-level code in those modules, and verifies the DocQA/chat
consumer files are unchanged.

The current source passed these local gates, including process exit and pytest
unconfigure, using the existing environment without synchronization:

- `r1-caller-contracts-verified.log`: 214 passed, including 142 extraction
  contracts and the existing DocQA, chat, graph and CLI caller checks.
- `r1-boundaries-packaging-verified.log`: 37 passed. The isolated `python -I -B`
  cold-import probe rejects runtime/UI imports and writes nothing in its fake
  working directory. Four distribution builds verify legal metadata as before;
  the actual ktem wheel and sdist must include `file_selection.py`.
- `r1-extraction-hooks-verified.log`, `r1-ci-ruff.log`, `r1-hygiene.log` and
  `r1-hygiene-baseline.log`: all exit zero; original Dev comparison is unchanged.

The coverage policy previously did not count `ktem_contracts`. An independent
negative case showed a changed statement there being ignored (0/0). The shared
module is now collected and counted in ktem's existing 50% floor and the same
90% production diff gate. Synthetic XML/JSON tests retain uncovered statements,
and path-combine tests now cover this fourth library root too. No local coverage
collector was started; the tests explicitly reject `Coverage.start`.

`push-c693160e.json` records the successful normal push and matching remote SHA.
The SHA had no existing run before dispatch. `dispatch-c693160e.json` and
`quality-runs-c693160e-started.json` record run `34445819877`, attempt 1, on that
exact head and original Dev base. The completed Ubuntu jobs at this SHA are:

| Ubuntu check at `c693160e`                                                                                        | Result                                                                                                                    |
| ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Static hooks, full CI Ruff, hygiene and original-Dev baseline comparison                                          | Passed                                                                                                                    |
| kotaemon Python 3.10 and 3.11                                                                                     | Each passed 371 tests, with 10 optional dependency skips                                                                  |
| ktem                                                                                                              | 2,786 passed                                                                                                              |
| benchmark and root contracts                                                                                      | 1,622 passed                                                                                                              |
| slide_cli                                                                                                         | Passed                                                                                                                    |
| Unified collection                                                                                                | Passed; 5,082 tests collected                                                                                             |
| Four clean wheel installations, frontend/browser security, Python distribution supply chain and both secret scans | Passed                                                                                                                    |
| Three dependency audit profiles                                                                                   | Failed: nine NLTK 3.10.0 GHSA findings per profile                                                                        |
| Three container audit profiles                                                                                    | Build/runtime smoke passed; seven NLTK CVE findings per profile                                                           |
| Coverage floors                                                                                                   | Passed: benchmark 90.22% / 90%; slide_cli 75.57% / 70%; kotaemon 70.11% / 60%; ktem including ktem_contracts 80.93% / 50% |
| XML/JSON exports and production diff                                                                              | Passed; production diff 94.82% (183/193 statements) against original Dev                                                  |

`dependency-audit-findings-c693160e.json` records the actual six failing jobs
and confirms the GHSA/CVE identifier sets are identical to R0. The image
secret scan completed successfully on this SHA; its earlier timeout is not
reported as a current failure. These are scanner findings, not an exploitability
assessment. No dependency upgrade or audit suppression was made.

The instrumented suites also completed successfully: root/benchmark 1,622;
kotaemon 371 plus 10 skips; ktem 2,786; and the complete slide_cli run. Raw logs
for all 20 jobs are retained as `ci-34445819877-job-*.log`. The aggregate job
`102782491452` records success for every required group except dependency and
container audits. Final run/job metadata are in `quality-34445819877-final.json`
and `quality-34445819877-jobs-final.json`.

[Coverage artifact 10141027869](https://github.com/262412/MARA/actions/runs/34445819877/artifacts/10141027869)
was downloaded and inspected. Its 623,616-byte ZIP matches GitHub's SHA256
`c4159163cafb92b458a64a51b1ac13888487687fc75fd4d567d7e03afc808966`.
It contains the combined `.coverage` data, `coverage.ini`, valid XML and valid
JSON. Its 1,001 raw file records contain no package-relative aliases; no removed
test-runtime files appear in the JSON. Artifact-derived package totals match
the CI log. The new `ktem_contracts/file_selection.py` has 22/22 covered
statements and no exclusions or missing statements. Both shared functions have
100% statement coverage. See `coverage-artifact-c693160e/inspection.json`.
`r1-downloaded-diff-coverage.log` independently recomputes the same 94.82%
production diff from that JSON against original Dev, without starting coverage
collection locally.

R1's fixed old-behavior characterization, exact two-function extraction,
legacy import/signature/staticmethod/patch compatibility, real callers, cold
import, distribution membership and applicable current-source gates are now
verified. The remaining six NLTK audit failures keep the complete Quality gates
workflow red; dependency changes and baseline suppression remain outside this
round's authorization. The two historical test directories remain because
automatic approval rejected their cleanup, as recorded above.
No R2 work is included.

## Historical evidence through 7496c6ae

All sections below preserve the earlier review and follow-up record. Their
NO-GO, unstarted R1 and unpushed statements apply to those historical snapshots;
the current decision, source SHA and completed CI results are recorded above.

**R0 remains NO-GO; R1 has not started.** The follow-up below repairs test
isolation, deterministic deadline checks and two confirmed Windows path-boundary
defects. Current supported-platform package and coverage gates remain required.
Skipped POSIX tests and historical CI are not current passes. The five earlier
R0 commits, through `89d99551a028ff4948bb40f0a06bcc24d24822cb`, were pushed at the
user's explicit request before this follow-up. This follow-up permits local
commits only and performs no new push, branch/worktree creation, branch switch,
merge, history rewrite, environment synchronization or R1/R2 extraction.

- Reviewed and fetched `origin/Dev`:
  `adab3f4d8f221e3620494fab0a24ef8e5557d12a` (the supplied audit base).
- Work branch: `codex/r0-r1-safe-refactor`, created from that Dev commit.
- Initial checkout: `main` at `412568ed41bfc92a7d11829b464e788065c7ac85`;
  existing local `Dev` remains `bc8074d0f724a3a1005a2637f4a1e867f56d68de`.
- Initial tracked changes: none. The existing untracked `NUL` and other
  worktrees were preserved. Runtime data and the existing `.venv` were retained.
- Evidence directory (outside Git):
  `D:\PythonProject\MARA-refactor-review-20260910-01a086ff`.
  `execution.jsonl` records wrapper commands, cwd, exit codes, duration and log
  paths; the other named logs retain direct-command and baseline evidence.

The primary checkout has an existing Windows CPython 3.10.19 environment.
The POSIX canonical wrapper requires `bin/python` and HPC mount paths that
are absent here; WSL reported no installed distribution. Tests used
`uv run --no-sync --offline --python 3.10 python`, with the three current
workspace libraries on `PYTHONPATH`, existing cached pre-commit environments,
`PYTHONDONTWRITEBYTECODE=1`, and a session `MARA_PYTEST_RUNTIME_PARENT` under
the evidence directory. No syncing/installing wrapper was substituted.
This is Windows source validation, not a claim of Ubuntu CI equivalence.

**Historical isolation exception from the original R0 full suite:** `PlatformDirs` on Windows
does not use the test's XDG cache override. `flowsettings.STORAGE["prefix"]`
resolved to the existing
`C:\Users\22826\AppData\Local\Cinnamon\Kotaemon\Cache\theflow`, outside the
session directory. Metadata inspection found new timestamped traces during
the final tests under `PrepareEvidencePipeline`, `TokenSplitter`, `ModelCliLLM`
and `ReadSlideTool`; the last two component directories were newly created.
`cache-audit.json` records the observed scope without reading trace contents.
No further runtime tests or cache cleanup followed in that checkpoint. There is
no pre-run snapshot of this cache, so this report does **not** claim that all
pre-existing runtime/cache contents were untouched. A Windows isolation fix
and proof of effective storage paths motivated the follow-up below.

## Historical R0 failure classification and changes

Public surfaces affected by the two bug fixes are QASPER candidate evidence
projection and retrieval-query context. CLI signatures, prompt templates, route
selection, numeric algorithms, authorization, schemas, metrics and runtime
directory isolation rules were not changed.

| Original failure                                                                  | Classification, authoritative contract and repair                                                                                                                                                                                                                                                                                                                                                                            |
| --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_required_slots_bind_semantically_to_final_selected_evidence`                | Outdated fixture. The physical-evidence identity rule introduced in `dd7f41ea` forbids reusing one physical identity for two required operands. The fixture now supplies two distinct selected spans on the same final page, each worth 4.2; it still tests rebinding from the preliminary page. `test_required_operand_slots_cannot_reuse_one_physical_evidence_identity` is retained unchanged.                            |
| `test_qasper_candidate_prompt_binds_typed_proposition_and_required_evidence_refs` | Implementation defect at the merge of canonical selector materialization (`dff0a8f0`) and cross-record contributions (`66e4912d`). A contribution ref could lack a canonical selector. Keep local plans and ordering; obtain missing selectors only when admitted by the joint canonical evidence universe. Added positive cross-record, orphan-rejection and missing-map fail-closed regressions. No raw-selector fallback. |
| `test_candidate_packing_prioritizes_relation_and_quantifier_over_record_id`       | Outdated expectation. Existing verifier priority (`256339a0`) sorts polarity before preferred IDs; candidate priority sorts relation/quantifier first. Fixed full expected order for both modes, preserving preferred-ID priority within equal polarity. Production ordering is unchanged.                                                                                                                                   |
| Two producer/runtime receipt tests in `test_fullsystem_runtime_barrier.py`        | Outdated fixtures: `benchmark-runtime` conflicts with the established `benchmark_*` basename rule. Changed only the two fixture basenames to `benchmark_runtime`; rejection and isolation tests remain. Native pytest skips these on Windows. A separate Git Bash check exercised the real producer and barrier, including invalid-basename rejection.                                                                       |
| `test_c9b8d385_true_unanswerable_recovery_uses_selected_document_title`           | Implementation defect: passive type questions receive a synthetic `define` predicate and lose required selected-paper context. Added a bounded generic type-question grammar; unknown actor, single selected/active document and title requirements remain. Added three positive, three explicit-relation/actor negative and two selection-negative cases. No case-ID branch.                                                |
| `test_docqa_contract_characterization.py` isort                                   | Import-order correction only.                                                                                                                                                                                                                                                                                                                                                                                                |
| `qasper_answer_relation.py` codespell token anchor                                | The reported token is the actual result of `_stem("languages")`. Use that expression in the same anchor set, preserving stemming behavior; no global spelling exclusion or literal replacement with a different token.                                                                                                                                                                                                       |

Historical [quality run 33939529781](https://github.com/262412/MARA/actions/runs/33939529781)
was read live. Its coverage job failed at **3 failed / 1,523 passed** in the
benchmark test stage, before any coverage-floor report. A threshold violation
was not established by that log (`coverage-ci-excerpt.txt`).

The first candidate repair used joint plan priorities globally. The complete
ktem suite exposed a regression in the frozen eight-record stage-2 fixture
(required `E7:S14` disappeared). That version was not accepted: the final
repair retains per-record priorities and uses joint evidence only for missing
canonical contributions. Its in-progress coverage-script run was interrupted
at 47%; that run is neither a complete suite nor coverage evidence for the
final revision.

Cross-record cases now require an additional canonical preparation only when
local refs lack materialized selectors. The candidate transaction is passed
through; provider latency and benchmark throughput have not been measured.

## Historical verification evidence

All Python rows below use the common no-sync command above. Unless specified,
cwd is `D:\PythonProject\MARA`. The PowerShell evidence `run.ps1` supplies only
the environment and logging described above. Full logs, including failed
intermediate runs, are retained rather than overwritten.

| Check / Python arguments after the common command                                                                              | Actual result and evidence                                                                                                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Original six node IDs, before repairs                                                                                          | 4 failed, 2 existing POSIX skips; `r0-six-baseline.log`.                                                                                                                                                                                        |
| Newly added defect regressions, before production fixes                                                                        | 5 failed, 6 passed; `r0-new-regressions-before.log`.                                                                                                                                                                                            |
| Focused R0 modules after the initial fixes                                                                                     | 61 passed, 10 existing skips; `r0-regressions-final.log`. Superseded for candidate priority by the final checks below.                                                                                                                          |
| `-m pytest -q`, cwd `libs/slide_cli`                                                                                           | Exit 0, 131 passed; `r0-cli-full.log`.                                                                                                                                                                                                          |
| `-m pytest -q`, cwd `libs/kotaemon`                                                                                            | Exit 1, 5 failed, 358 passed, 15 skipped; `r0-kotaemon-full.log`. Four failures require FIFO/symlink support or privileges; one assumes XDG cache resolution on Windows.                                                                        |
| Complete ktem suite under the first candidate repair, `-m coverage run ... -m pytest -q libs/ktem/ktem_tests`                  | Exit 1, 103 failed, 2,541 passed; `r0-ktem-coverage.log`. Includes the subsequently corrected selector regression, Windows filesystem failures and two sub-200ms deadline assertions. This is an intermediate result.                           |
| `scripts/check_pytest_collection.py --minimum 1260`                                                                            | Exit 0, 4,841 collected; `r0-unified-collection.log`. Collection is not execution. The contract's old warning about root collection conflicts does not describe this snapshot's collection result.                                              |
| `-m ruff check . --exclude *.pyi --exclude .playwright-cli --exclude .superpowers`                                             | Exit 0; `r0-ruff.log`.                                                                                                                                                                                                                          |
| `scripts/check_codebase_hygiene.py`                                                                                            | Exit 0; `r0-hygiene-all.log`. Baseline was not refreshed.                                                                                                                                                                                       |
| `scripts/check_hygiene_baseline.py --base-ref origin/Dev`                                                                      | Exit 0; `r0-baseline-ratchet.log`.                                                                                                                                                                                                              |
| `scripts/sync_locked_constraints.py --check`, `scripts/check_container_lock_parity.py`, `scripts/check_supply_chain_policy.py` | All exit 0; matching `r0-*.log` files.                                                                                                                                                                                                          |
| `uv lock --check --offline --python 3.10` and Docker-project equivalent                                                        | Both exit 0; 404 / 312 packages; `r0-root-lock.log`, `r0-docker-lock.log`. No synchronization.                                                                                                                                                  |
| `npm run test:frontend`                                                                                                        | Exit 0, 18 passed; `r0-frontend.log`. The workflow step label saying 19 is stale.                                                                                                                                                               |
| Git Bash `check-runtime-receipts.sh` in the evidence directory                                                                 | Exit 0, three assertions: invalid basename rejected without a directory, exact producer-owned receipt, and fail-closed barrier exit 2 preserving the runtime; `r0-git-bash-receipts.log`. This does not relabel skipped pytest cases as passed. |

Final review checks:

| Check                                                                                    | Result                                                                                                                                                                                           |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Original six node IDs on the final repair                                                | Exit 0, 4 passed, 2 existing POSIX skips; `r0-six-reviewed.log`. Exact arguments are in `execution.jsonl`.                                                                                       |
| Cross-record, frozen stage-2, semantic-pack and candidate modules on the narrowed repair | Exit 0, 18 passed; `r0-selector-narrowed.log`. No existing stage-2 or transaction assertion was weakened.                                                                                        |
| `-m coverage run ... -m pytest -q libs/slide_cli`, cwd repository root                   | Exit 0, 131 passed; `r0-cli-reviewed.log`.                                                                                                                                                       |
| Whole-repository Ruff, hygiene and baseline ratchet                                      | All exit 0; `r0-ruff-reviewed.log`, `r0-hygiene-reviewed.log`, `r0-baseline-reviewed.log`.                                                                                                       |
| `-m pre_commit run --files <nine changed Python files and this document>`                | Exit 0; `r0-precommit-reviewed.log`. Black and line endings were corrected in the preceding run. Hooks with no applicable files were skipped.                                                    |
| Two deadline assertions without coverage                                                 | Exit 1, 1 failed / 1 passed; `r0-deadline-diagnostic.log`. The DocQA case still measured 0.203s against `<0.2s`. Root cause is unresolved; it is not attributed solely to instrumentation.       |
| Read-only public/import/protection comparison                                            | Exit 0; `r0-diff-review.log`. Public signatures are unchanged, the only added production import is standard-library `re`, and protected paths plus the original `NUL` digest match the baseline. |

Complete package and coverage results are recorded in the review completion
below.

Remaining platform blockers include missing secure `dir_fd`/`O_DIRECTORY`/
`O_NOFOLLOW` operations and `fchmod`, Windows symlink privileges, unavailable
FIFO, POSIX filename/path/mode assumptions, open-file replacement semantics,
and byte-for-byte vendor-license checks affected by CRLF checkout. These are
not repaired by weakening security checks, changing expected failures or
normalizing vendored licenses. Full Ubuntu package/coverage gates still need
an existing suitable environment or a separately authorized setup change.

Not executed: clean wheel install, container builds/runs, desktop Gate 2,
browser malicious-content smoke, dependency-vulnerability/secret scans,
provider/model probes, Slurm jobs and benchmark dataset runs. No network
model call was intentionally initiated. Package unit tests do not establish
benchmark artifact completeness or end-to-end UI readiness.

## Historical tracked repository map

Inventory reads `git ls-tree` and blobs at the Dev base, not the working tree's
runtime directories. `repository-map.json` records every tracked path with its
role/area, Python imports and exports, dynamic-entry candidates, JS import
edges and static components. `inventory.py` and `inventory-summary.json` in
the evidence directory reproduce the measurements.

Measured: **2,436 tracked files**, **1,818 Python modules parsed** (zero parse
errors), including **1,129 production Python modules**. There are **5,437
explicit internal Python edges**, **8,604 with parent-package initialization
edges**, and **24 production static strongly connected components** (largest
sizes 237, 32, 15, 15). Lazy/conditional imports are included: these are
inspection candidates, not proof that all such cycles execute at runtime.
JS scanning resolved 209 internal import occurrences; 160 external/unresolved
specifiers remain explicit. Dynamic candidates total 1,498: 744 calls,
383 event bindings and 371 classpath/patch strings, followed by manual seam
inspection. These counts are not counts of independent public APIs.

The separate frontend inventory records 1,306 occurrences: 95 literal element
IDs, 29 class declarations, 203 DOM selector calls and 979 CSS rule candidates.
Computed selectors and template interpolation are not statically resolved;
these are source locations for review, not a browser-execution proof.

| Area (tracked files)                                     | Ownership, entries, compatibility/dynamic boundaries and verification                                                                                                                                                                                                                                                                                                                                                |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `libs/slide_cli` (50)                                    | `slide_cli.cli:main` owns both `MARA` and `MARA-cli`; deck/workspace commands and lazy DocQA/kotaemon groups. Preserve Click options, JSON/exit codes, session files and optional-heavy-import boundaries. Tests in this package cover the public shells and adapters.                                                                                                                                               |
| `libs/kotaemon` (396)                                    | Model/embedding, loader, indexing/retrieval, agent/MCP, storage and platform-support primitives. Provider configuration uses string classpaths; platform assets use `importlib.resources`. External model/storage/office tools are integration seams. Package tests cover agents, MCP, CLI adapters, settings, artifacts and providers with substitutes.                                                             |
| `libs/ktem` (954)                                        | App bootstrap, Gradio UI, DocQA runtime/planning/evidence/verifiers, index/file/graph lifecycle and preview. `ktem.__init__` bootstraps settings; `docqa.__init__` imports runtime/execution; `utils.__init__` imports conversation/dependencies/language. These parent imports matter for light helpers. SQLModel/Gradio/model/index integrations require ktem, event, security, persistence and cold-import tests. |
| `apps/desktop` (156)                                     | Electron main/preload/renderer IPC and sidecar manager bridge HTTP to FastAPI routes/application and `DocQARuntime`. Preserve handshake, cancellation, error envelopes, file authorization, streaming and journal terminal states. `shared/api-contracts.generated.ts` is generated from OpenAPI. Sidecar tests and desktop Gate 2 remain distinct from Web tests.                                                   |
| `benchmark` (459) and root `tests` (34)                  | Dataset adapters, execution, scorers, evidence/semantic contracts and regression fixtures. Dynamic model/component configuration and frozen example artifacts are contractual. Root tests cover delivery, storage, security and environment/coverage scripts. A passing runner process is not artifact acceptance.                                                                                                   |
| `scripts` (115), `.github` (16), `docker` (2), root (37) | Slurm producer/consumer receipts and runtime isolation, environment/install wrappers, source/lock/coverage gates, four distribution packages, Docker lite/full/ollama targets and release workflows. Preserve directory/receipt schemas, environment ownership, lock parity and packaged assets.                                                                                                                     |
| Platform/docs/config                                     | `.codex` (49), `docs` (106), `templates` (10), `local_backends` (3), `.githooks` (1), `.vscode` (1). Skills and templates are shipped API/resource consumers, not dead prose; platform specs and registry/manifests determine installed names.                                                                                                                                                                       |
| Auxiliary/generated/vendor                               | `.idea` (10), `.superpowers` (21), `.playwright-cli` (10), `.tmp_publish_check` (6) were classified, not removed. Vendored PDF.js archive/license/manifest and two LaTeX resource files retain licenses. Binary payloads, virtual environments, caches and user datasets were not traversed for code analysis.                                                                                                       |

The third-party `assets/js/svg-pan-zoom.min.js` (v3.6.2, with its upstream
header) is also classified as vendor and excluded from owned-source analysis.

Disjoint role totals: 1,183 source, 722 test, 309 docs/platform, 105
config/delivery, 31 auxiliary-history, 16 generated-artifact, 5 generated-lock,
19 asset, 1 generated-source, 39 fixture/resource and 6 vendor files.

Manual boundaries needing preservation:

- Click `_LazyDocQAGroup` / `_LazyKotaemonGroup` defer loading command modules.
  `kotaemon.agents.__init__` currently has eager exports despite the hygiene
  contract's lazy-load wording; this discrepancy needs separate characterization.
- Gradio `.then` and event input/output order, component attributes, cancellation
  and streaming are behavior. Patch strings in tests and classpaths in config
  remain consumers even when a static import appears unused.
- `chat_message_events.py` orders submit, runtime stream, request cache,
  selection clearing, PDF refresh, scroll, conversation naming, then non-demo
  persistence; `.success` and `.then` have distinct failure behavior.
- `chat_panel.py` creates `main-pdf-preview`, its iframe/shell and `chat-input`;
  `assets/js/main.js` queries those IDs/classes and `assets/css/main.css`
  styles them. `chat_layout.py` creates `chat-info-panel` / `html-info-panel`,
  which `pdf_viewer.js` reads during modal and scrolling actions. Renames need
  all producers/consumers and packaging reviewed together.
- `ktem.db.models` resolves `KH_TABLE_*` dynamically and may initialize tables.
  Conversation `data_source` JSON, user/public fields and `Settings.setting`
  are persisted contracts. `IndexManager` resolves `KH_INDEX_TYPES`; default
  settings load model/loader extensions. No migrations were made.
- `libs/ktem/MANIFEST.in` owns JS/CSS/icons/PDF.js resources. Frontend DOM/CSS
  selectors and loading order require browser verification, not just an import
  graph. Platform-support registry/specs own `.codex` / `.claude` resources.
- `kotaemon` upward dependencies include explicit app-init/CLI/request-adapter
  seams, plus citation-QA and Cohere-ranking application coupling. A blanket
  ban would break existing integrations; inspect each seam before moving it.

## Historical R1 location planning

R1 remains unexecuted; **zero duplicate implementations or internal dependency
edges were removed in this batch**. Both old modules and the `DocQARuntime` /
`ChatPage` staticmethod/patch paths are unchanged. A suitable future neutral
location is `libs/ktem/ktem_contracts/file_selection.py`: its parent currently
contains only a package docstring and `ktem_contracts*` is included in packaging.
Importing a module under `ktem.docqa` or `ktem.utils` would invoke heavier parents.

Callers include runtime session/turn/mutation services, `ChatPage` and chat
knowledge-graph runtime. Preserve old exports/signatures and test
`test_chat_source_scope`, `test_docqa_runtime_helpers`, runtime callers and
isolated cold imports. Before extraction, fixed-expectation tests must cover
None/empty/scalar/list/tuple, duplicates, whitespace, 0/False, order, exceptions
and input immutability: normalize preserves repetitions/whitespace and
stringifies 0/False; merge strips/deduplicates and discards 0/False. Keep UI
selector adaptation and the separate `chat_submit_sources` helper out of R1.

Priority after restoring the gates: R1 pure selection duplication (small,
bounded benefit); R2 parent-package and runtime composition boundaries (high
import/lifecycle risk); R3 one Web event workflow at a time (event-order risk);
R4 one planning/evidence/execution rule boundary (very high semantic risk);
R5 one storage/index/graph/session/artifact lifecycle (authorization/data risk);
R6 CLI/desktop/benchmark/delivery cleanup with package/resource compatibility.
No later phase is authorized by this report. Each needs its own characterization,
package gate, actual diff review and independent acceptance.

## Historical original R0 review completion

The changed-file set is limited to:

- Production: `libs/ktem/ktem/docqa/qasper_answer_relation.py`,
  `libs/ktem/ktem/docqa/typed_retrieval_recovery.py`,
  `libs/ktem/ktem/reasoning/mara_qasper_candidate_selector_projection.py`.
- Existing tests: `benchmark/tests/test_fullsystem_runtime_barrier.py`,
  `libs/ktem/ktem_tests/test_docqa_calculation_plan.py`,
  `libs/ktem/ktem_tests/test_docqa_contract_characterization.py`,
  `libs/ktem/ktem_tests/test_mara_qasper_candidate_input_priority.py`.
- Added files: `libs/ktem/ktem_tests/test_docqa_generic_recovery_context.py`,
  `libs/ktem/ktem_tests/test_qasper_cross_record_selector_projection.py`,
  and this document.

At the user's request, the repairs were committed locally on
`codex/r0-r1-safe-refactor`, above the unchanged audit base
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`:

- `1651eed2`: canonical cross-record selector repair and regressions.
- `60a311de`: generic type-question recovery context and regressions.
- `bd75fe1d`: evidence, priority and runtime-receipt fixture corrections.
- `dacca8b1`: import-order and semantics-preserving spelling fixes.

The reviewed implementation checkpoint is `dacca8b1`; this record is delivered
in a following documentation commit. Each staged diff passed
`git diff --cached --check`. Committing does not change the R0 NO-GO decision.
At that commit-preparation checkpoint, no push or merge had occurred and no
additional runtime tests were run. The user subsequently requested and
authorized pushing the five original commits through `89d99551`; the follow-up
below does not push again.

To roll back the implementation while preserving history, revert only these
four commits in reverse order:
`git revert dacca8b1 bd75fe1d 60a311de 1651eed2`.
The documentation commit may be reverted separately if desired. Check for
new work before any rollback; the pre-existing `NUL`, runtime data,
environment, other branches and worktrees are outside this batch.
No rollback has been executed.

Final complete suite results:

| Command after the common Python prefix (cwd repository root)                                  | Result                                                                                                                                                                                                                                                                                     |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `-m coverage run --rcfile=<evidence>/coverage/coverage.ini -m pytest -q libs/ktem/ktem_tests` | Exit 1; **2,542 passed / 102 failed** in 774.22s; `r0-ktem-reviewed.log`. Failure-list comparison with the intermediate run removes only the selector regression; no new failed node IDs. See the follow-up's per-node classification: these cannot all be described as platform failures. |
| `scripts/run_coverage_gates.py --output-dir <evidence>/coverage-gates-reviewed`               | Exit 1 at its first suite, `benchmark/tests tests`: **1,488 passed / 11 failed / 27 skipped** in 804.17s; `r0-coverage-gates-reviewed.log`. Package floors and the script's final reports were not reached.                                                                                |

The eleven benchmark/root failures are: five Windows symlink privilege cases;
two POSIX Bash launch cases (the bare `bash` resolves to the WindowsApps alias,
with GBK decoding warnings obscuring stderr); the POSIX `.venv/lib/python*/`
fingerprint assumption; missing `sha256sum` on PATH; the Windows cache-isolation
failure above; and the long-document fixture's byte preflight (4,510 checkout
bytes versus 4,471 bytes in the Git blob because of CRLF). The latter failed
before exercising the runtime recovery query; its assertion/fixture was not
weakened. The separate original-six and generic-recovery unit results remain
as listed above.

Final-revision coverage data from the completed ktem, CLI and benchmark/root
runs was combined with `coverage combine --keep`, preserving the original
data. Changed modules measure 88.60%, 96.33% and 98.95% respectively
(`r0-coverage-changed-modules.log`). The repository's
`calculate_diff_coverage` evaluator, supplied the **then-uncommitted diff**
against the Dev base, reported **100.00% (17/17 changed production statements)**
at the unchanged 90% minimum (`r0-working-diff-coverage.log`). The ordinary
CLI compares committed HEADs, so the external `working_diff_coverage.py`
adapted diff collection for that measurement. Committing preserved the
measured source contents. This partial aggregate
is evidence for the repair lines, not a passed full coverage gate; the four
package floors remain unverified.

**Stop at independent R0 review.** Restoring supported-platform package gates,
resolving the timing failures and proving cache isolation come before R1.

## Historical R0 follow-up through 7496c6ae

The reviewed input HEAD is `89d99551a028ff4948bb40f0a06bcc24d24822cb`; the fixed
comparison base remains `adab3f4d8f221e3620494fab0a24ef8e5557d12a`.
All new evidence is under the original evidence directory's `followup/`.
`execution.jsonl` records the exact argv, cwd, exit code, duration, input HEAD
and SHA256 of every changed/new Python file for each run. `versions.json`
records CPython 3.10.19, pytest 8.4.2, coverage 7.10.7, pre-commit 4.3.0,
SQLAlchemy 2.0.43, theflow 0.8.6, platformdirs 4.4.0 and uv 0.11.19.
The command prefix is still `uv run --no-sync --offline --python 3.10 python`.
Unless stated otherwise, cwd is `D:\PythonProject\MARA`.
The final implementation HEAD is
`dffd695497a074895da72216ea8155874f016ffb`; the documentation commit follows it.
`head-*` execution records name this exact SHA with no uncommitted Python
changes. `source-equivalence.json` compares the earlier focused checks' file
hashes with this implementation, so their former input HEAD is not mistaken
for a test of unchanged `89d99551` source.

### Changes and public boundaries

- Test infrastructure: `pytest_runtime_isolation.py`, new
  `pytest_runtime_plugin.py`, root `conftest.py`, and the kotaemon/slide_cli
  `tests/conftest.py` files. All three entrypoints activate the same owned
  session before business imports. Tempfiles, inherited desktop settings,
  NLTK resources, actual storage settings and cleanup ownership are covered.
  Bundled NLTK resources are copied read-only into the session. SQLAlchemy
  pools and theflow caches are closed only for session-owned paths.
  Cleanup runs at pytest unconfigure so test results remain visible if a
  resource cannot close. A regression covers read-only owned Git fixtures;
  the narrow Windows unlink repair requires a regular, read-only file inside
  the owned root. Other cleanup errors are still raised.
- Necessary bootstrap changes: `ktem/runtime_bootstrap.py` and
  `ktem/default_flowsettings.py`. An explicit test flag selects owned
  config/data/cache paths and rejects external configured paths before I/O.
  Test configuration does not search source/user parents for `.env`.
  Without that flag, normal PlatformDirs and Desktop path selection remain;
  an explicitly configured NLTK directory is respected. No DB schema,
  provider record, CLI signature, UI event chain or production timeout changes.
- New protection tests: `tests/test_runtime_isolation_bootstrap.py`,
  `tests/test_runtime_isolation_subprocess.py` and
  `tests/test_runtime_isolation_entrypoints.py`. They check actual SQLite,
  storage traces, files/output writes, child/grandchild inheritance, both
  initialization orders, early rejection and ownership-aware cleanup.
  Package-cwd probes execute their real conftest entrypoints. The source
  bootstrap path is asserted against this checkout.
- Existing fixture corrections: `test_preview_cache_roots.py` temporarily sets
  `USERPROFILE` as well as `HOME`; `test_workspace_flowsettings_storage.py`
  explicitly activates its child runtime and checks its resolved storage root.
  Both retain their behavioral assertions.
- Confirmed Windows security defects: `ktem/index/file/deletion.py`,
  `ktem/index/file/storage_lifetime.py` and `ktem/preview/service.py` now reject
  path anchors, including rooted paths without a drive, before joining them
  to trusted storage. Existing deletion/preview/storage negative cases cover
  the failure. The preview test also blocks external mkdir if rejection ever
  regresses; the storage test requires the intended typed error. POSIX
  descriptor, symlink, identity, atomic publication and vendor checks remain.
- Deadline tests: `test_docqa_route_deadline.py`, `test_mara_route_deadline.py`
  and new `route_deadline_test_helpers.py`. Only the two wall-clock unit tests
  use a controlled unresponsive worker/clock. Their state/evidence assertions
  remain, with explicit waits of 0.08s and 0.10s and one worker start. All six
  real timeout/cancellation integration tests remain unchanged.

The deadline implementation reserves 20ms from the 100ms test request, then
allows an additional 100ms cancellation grace. The old `<0.2s` assertion had
little room for scheduling and clock granularity. `observe_deadline.py`
recorded waits of 0.08478s and 0.10849s; elapsed perf-counter time was 0.19752s
while the production monotonic trace reported 0.204s. That diagnostic exited
1 because the then-open SQLite pool prevented cleanup; its timing observation
is not a passed gate. The deterministic tests do not assert that an
unresponsive backend physically stops within the nominal request budget.
Real integration tests separately check cancellation once, cooperative stop,
late-result rejection, no late evidence/authority, and unchanged defaults.

### Isolation incident and retained evidence

The first package-cwd attempts in this follow-up did not load root conftest.
Consequently their apparent test passes were insufficient isolation evidence.
The unisolated kotaemon run updated the actual profile's `.env`, `.env.example`
and `flowsettings.py` at 09:03:35, and cache metadata contains 335 entries
updated since follow-up start. This is a validation error in this follow-up;
it is not attributed only to the previous R0 run.

`known-runtime-metadata.json` and `user-cache-before-final.json` record observed
metadata without exposing configuration contents. The known profile and
repository SQLite files retain August modification times. There is no complete
pre-run snapshot, so neither original configuration contents nor every runtime
byte can be certified unchanged. No verified pre-run config backup was found
in the profile directory. Observed config files were preserved separately in
`config-observed-after-package-run/`; that is an after-event copy, not a
restoration source. No user cache/config was deleted, moved or guessed back.

After adding package entrypoint activation, the controlled 42-test run and CLI
suite produced zero metadata changes against the retained user-cache,
office-cache and canonical NLTK snapshot. The final focused check adds the
read-only cleanup case for 43 passes. `user-cache-after-final.json` and
`final-runtime-footprint.json` record the post-suite comparison, including
config bytes against the retained after-event copy. The final comparison finds
zero added/changed/removed cache entries, identical retained config bytes,
unchanged observed SQLite metadata and no remaining coverage bootstrap files.
These comparisons cannot
recover or certify the original pre-run state. The first ktem and coverage
attempts were interrupted when additional isolation gaps were discovered;
their logs remain and are not counted as completed gates.

Coverage instrumentation also wrote temporary `subcover_<pid>.pth` files in
the canonical `.venv` and its `Lib/site-packages`. The installed coverage
7.10.7 `patch=subprocess` implementation creates these files itself; disabling
bytecode writes does not prevent them. Two interrupted task-owned coverage
processes left four such files. Their process IDs, timestamps and exact
coverage bootstrap bytes established ownership; copies and the removal
record are in `coverage-bootstrap-cleanup/`. Only those four owned files were
removed. Local full coverage was not retried after discovering this behavior,
because it conflicts with the required canonical-environment write boundary.
No dependency installation, synchronization or upgrade was performed.

The first final-HEAD benchmark/root run exposed one new invocation problem:
the evidence-directory prefix made an atomic cache temporary path exceed this
Windows runtime's path limit. Only `MARA_PYTEST_RUNTIME_PARENT` was shortened
to `D:\MARA-r0-pytest-01a086ff`; every session still uses a unique ownership
marker and the same isolation plugin. The failing diagnostics case passed
under that parent (`head-root-short-path-regression.log`, exit 0, 1 passed).
Source, cache naming, fixture bytes and assertions were not changed.

### Historical failures and current gates

`historical-failure-nodes.json` maps all 118 failures from the three original
final suite logs to exact node IDs, log line ranges, error excerpts and reasons:
3 production/infrastructure defects, 2 test-clock/synchronization failures,
79 platform-capability or platform-semantics cases, 29 permission/tool failures,
2 CRLF/fixture-byte differences and 3 unconfirmed causes. The vendor LICENSE
and frozen QASPER document byte assertions remain unchanged.

The unconfirmed nodes are the equal-length rewrite download test, the two-fresh
DocQA POSIX launcher test, and the documented secret-file-permission shell
test. A likely platform mechanism is documented where supported; their
underlying failures are not relabeled as confirmed without adequate evidence.

| Current-source check                                                           | Result and log in `followup/`                                                                                                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Actual isolation, subprocess/entrypoint and compatibility regressions          | Exit 0, 43 passed; `r0-cleanup-and-entrypoints-final.log`. Includes read-only fixture cleanup and default production-path compatibility.                                                                                                                                                                                                                                                  |
| Windows root/path security regressions                                         | Exit 0, 6 passed; `windows-root-paths-after.log`. The protected pre-fix run failed 3 cases. The same nodes pass in the final complete ktem suite.                                                                                                                                                                                                                                         |
| Original six, recovery/selector negatives and deadline/cancellation cases      | Exit 0, 27 passed / 2 POSIX skips; `r0-original-and-negative-final.log`. Source hashes distinguish later test-cleanup changes; the same executed nodes pass in the final full suites. Receipt skips still require real Linux execution.                                                                                                                                                   |
| `-m pytest -q`, cwd `libs/slide_cli`                                           | Exit 0, 131 passed; `head-slide-cli-full.log`.                                                                                                                                                                                                                                                                                                                                            |
| `-m pytest -q libs/ktem/ktem_tests`                                            | Exit 1, 2,547 passed / 97 failed in 307.73s; `head-ktem-full.log`. Five historical failures resolved. Frozen stage-2, transaction and security-negative assertions were retained.                                                                                                                                                                                                         |
| `-m pytest -q`, cwd `libs/kotaemon`                                            | Exit 1, 359 passed / 4 failed / 15 skipped in 113.09s; `head-kotaemon-full.log`. Four failures concern FIFO/symlink capability or permission. After the summary, unconfigure also raises WinError 32 for the Chroma/HNSW `data_level0.bin` held open on Windows.                                                                                                                          |
| `-m pytest -q benchmark/tests tests`                                           | The first final-HEAD run returned exit 1, 1,517 passed / 11 failed / 27 skipped in 387.52s; `head-root-benchmark-full.log`. Ten historical failures remain and one long test-root path failure was introduced by the invocation. With the shorter owned parent, exit 1, 1,518 passed / 10 failed / 27 skipped in 367.52s; `head-root-benchmark-short.log`. No new failed node IDs remain. |
| Full `scripts/run_coverage_gates.py --output-dir <followup>/coverage-isolated` | Intermediate source only, exit 1: first suite reached 100% but read-only owned fixture cleanup failed before the usual summary; `r0-isolated-coverage-complete.log`. That cleanup is now covered and fixed. No current-HEAD full coverage run followed discovery of coverage's canonical-environment `.pth` writes. No package floor was reached.                                         |
| Full Ruff, hygiene, baseline against exact Dev SHA                             | Exit 0; `head-ruff.log`, `head-hygiene.log`, `head-baseline.log`. Baseline was not refreshed.                                                                                                                                                                                                                                                                                             |
| Changed-file pre-commit and final diff whitespace checks                       | Python source checks passed with exit 0 in `r0-final-static-pass.log` (all 20 Python file hashes match final implementation). Final report pre-commit and `git diff --check` also pass with exit 0; `head-report-static-pass.log` and the staged commit record.                                                                                                                           |

`head-suite-comparison.json` contains exact final failed node IDs, resolutions
and category counts against the original three complete logs: seven historical
failures resolved, 111 remain, and no new failed node IDs. All four package
coverage floors remain required: benchmark 90%, slide_cli 70%, kotaemon 60%
and ktem 50%. No changed-lines result substitutes for these floors.

The bounded read-only Barkla SSH retry still fails with
`Control socket connect(...codex-jump-relay-lxe): Connection refused` (exit 1).
No WSL distribution or suitable local Linux/container runtime is available.
The work-branch CI query found no runs. Its remote HEAD is the earlier
`89d99551`; follow-up source has not been pushed, so dispatching that old
revision would not validate these changes. `environment-blockers.json`
records the exact branch/base, command and missing execution/synchronization
conditions. No old CI result substitutes for the current source, and no new
environment was installed or synchronized.

**R0 NO-GO; R1 not started.** Complete supported-platform suites, both POSIX
receipt executions, package coverage floors and the remaining diagnostic/
cleanup issues are still outstanding. No characterization/extraction into
`ktem_contracts.file_selection` has begun. Stop here without R2.

Four new local implementation commits retain the five reviewed commits:

- `c6032903`: runtime entrypoint/ownership and path-boundary protection tests.
- `0e49aea1`: test isolation, bootstrap boundaries and fixture corrections.
- `c08cc1bc`: reject anchored paths before storage operations.
- `dffd6954`: deterministic deadline unit checks and shared test helper.

This existing report is delivered in a separate fifth local documentation
commit. `final-git-state.json` records its actual full HEAD, status, branch,
commit range and remote comparison. Each staged diff passes
`git diff --cached --check`; the pre-existing untracked `NUL` remains.
No follow-up push, PR, merge, branch/worktree creation, branch switch, reset,
clean or history rewrite was performed.

For a history-preserving implementation rollback, review later work first and
revert only `dffd6954 c08cc1bc 0e49aea1 c6032903` in that order. The documentation
commit is separate. This does not revert the five earlier commits or restore
external profile/cache contents. No rollback was executed.
