# Safe-refactor status

## Current actual utility-call diagnostic checkpoint: R6-A/U1 (2026-09-26)

**R6-A/U1 remains BLOCKED.** One preregistered diagnostic group completed:
Edge 5/5 and matching Playwright Chromium 5/5 reached their intended exit
boundaries, but the target Login stall was not reproduced under observation.
There is no established product defect/fix or environment disposition from
this group. No further App was launched after the group. Natural five-exit
acceptance, selector/U1 browser regression, primary 37, confirmation 37 and
new Quality CI are **NOT RUN** this round. Diagnostic success does not replace
the retained natural **4 passed / 1 failed** exit batch.

Baseline is `d84b3eabe9ceccd6bb96a0b58d2e5d967de8fca4`; its prior harness is
`79a3f36ef65219c593c078a2f9f23a675fdb02cf`. Actual App diagnostics used the frozen
`e15a500db38e779122d3ce27250fc33584907bd9` source/test/harness. The final observer
error-label correction and unit test are
`fa8d8a276230a3d3185014a6afd88e55603651eb`; **no App run is attributed to that
later tree**. No production file changed. Selector fix `7f29ce87` and all
accepted stages remain. R5 is ACCEPTED; R6-A is not ACCEPTED; S1/PCRE2 is OPEN,
merge/release is NO-GO, and no R6-B/C/D was started.

Evidence parent is `D:/PythonProject/MARA-refactor-review-20260910-01a086ff/`.
This round is `r6a-u1-recovery/actual-stability/` (A). Bounded-acceptance (B),
login-frame (L), protection-selector (E) and earlier evidence remain intact.
The B archive was verified before any App: SHA-256
`43d5e729ef8d1dc79af7d87aa3debc322fa80b5a4bf2609c5e1e6a37d7a50d5e`, 133
members, CRC check passed. Prior fd44 primary **37/37** and confirmation
**16 passed / 1 failed / 20 NOT RUN** remain separate; no batches are combined.

### Actual installed call and observer boundary

Installed Playwright is **1.61.1**. Its physical `playwright-core/lib/coreBundle.js`
has SHA-256 `6be5c2ea035554e9b184b1dbc7aa5e7f1fb428dd1b5c202022858dcfae9bee27`.
The decoded generated `source4` injected program has SHA-256
`9e3eee05873e664c48f2b7993edfb90cd505137486fba5eeea9cc5ec20468e2f`.
The loaded Node script and actual utility injection wrapper/options were
checked against these bytes before installing points. Nine Node and thirteen
utility false-condition logpoints bind to the real loaded script IDs and
resolved source lines. They observe:

`_performPointerAction -> evaluateInUtility -> utilityContext -> actual Runtime.callFunctionOn(awaitPromise=true) -> checkElementStates -> _checkElementIsStable -> saved builtin rAF -> callback/check -> fulfill or reject -> stableResult -> native protocol response -> Node pointer result`.

The opt-in `MARA_BROWSER_STABILITY_DIAGNOSTIC=1` is limited to this group;
both FRAME_DIAGNOSTIC and legacy LOGIN_DIAGNOSTIC were **0**. Natural default
remains off. The observer uses the existing Playwright utility context in the
actual App, strict DOM-node identity, context unique ID, frame/loader, actual
API action and native protocol request/session IDs. It creates no extra world,
page timer or rAF request, replaces no builtins, resolves no production Promise,
and uses no forced/Enter/API/DOM Login, universal access or parameter sweep.
Owned bindings and bounded records are diagnostic state, not product APIs.

Each trace retains lifecycle creation/destruction, point installation,
streamed hits, snapshots, explicit gaps/caps and cleanup. There were no
unexpected pauses, dropped records, observed condition/binding errors or
outstanding protocol replies in the ten completed traces. `actual-call-analysis.json`
also checks every raw error field independently of its phase label.

### One bounded group, actual identities and evidence ceiling

`diagnostic-plan.json` was written before execution and `frozen-inputs.json`
pinned 133 source/test/harness entries, 135 protected raw files, dependency
inputs, runner scripts and 12 runtime-file hashes, including browser DLLs.
The group ran **13:11:57.743 to 13:21:25.878 UTC**, with no retries. Every App
used a fresh owned runtime/profile/cache, serial startup and exclusive port
8768, with the same Gradio **4.39.0** frontend bytes and original 30-second
mouse-click budget. Argument equality was checked within each browser arm.

| Diagnostic exit case | Edge 153.0.4234.48            | Chromium 149.0.7827.55        | Outer / Node / App exit in both arms |
| -------------------- | ----------------------------- | ----------------------------- | ------------------------------------ |
| Normal               | PASS, held reached            | PASS, held reached            | 0 / 0 / 0                            |
| Assertion            | PASS, exact injected primary  | PASS, exact injected primary  | 1 / 1 / 0                            |
| Node watchdog        | PASS, held then watchdog      | PASS, held then watchdog      | 1 / 1 / 0                            |
| App watchdog         | PASS, held then watchdog      | PASS, held then watchdog      | 1 / 1 / 1                            |
| Release failure      | PASS, held then release fault | PASS, held then release fault | 1 / 0 / 1                            |

All ten actual stability calls entered the rAF callback twice, read two equal
rectangles, fulfilled with `true`, continued through visible/enabled checks,
and returned `undefined` successfully to the Node pointer caller. Each native
protocol request matched its response. The observed first-callback delays
were 3.4-4.1 ms and first-schedule-to-fulfill values 7.5-9.3 ms; these are
instrumented trace timings, not performance measurements of natural runs.

For the Edge fifth case, frame is `F4A624F869A42776453CD53957D74220`, loader
`2FE716ED802B386CD4B3BBA6FB0A7F64`, utility unique ID
`-4779775196422681100.-160177821994352209`, Login backend node **7**, Node PID
**28648**, action `call@41`, and protocol ID **104** in session
`1507F69A14A70F504C66053715B05E2A`. Its held business session is `1j1pcfbiy2s`.
The Chromium fifth case uses frame `1A260DE316CC91825BAD57E573E5C87B`, loader
`E61FF0E8C0EDF0CA4E88187E1005F202`, utility unique ID
`-741335135701379014.5395829502328531562`, backend node **4**, Node PID **22324**,
and protocol ID **104** in session `48C75372E4C851292D52A9492038E951`;
its held business session is `48ei2mty0fn`. IDs are scoped to their case/process/
CDP session, not correlated merely because `call@41` or 104 repeat.

The saved rAF reports native function text and differs from the current global
function. The pinned generated source explicitly uses `.bind(global)` when
saving builtins, so that inequality does **not** establish function replacement.
The `raf-first` hit is before the real native registration and `promise-return`
after it; the production code discards the registration ID, so none is invented.
Actual callback hits and downstream continuation prove return for these calls.
The reject point was installed but not exercised; a missing reject hit is not
failure-path validation. The generated rectangle itself maps top/left into
its x/y fields; evidence retains that representation unchanged.

System Edge was neither installed over nor updated. Chromium revision **1228**
was installed once from the pinned Playwright registry into
`D:/MARA-s1-01a086ff/actual-stability-browsers`, using channel `chromium`, full
new-headless Chromium and no headless-shell fallback. Engine version, vendor
defaults, fresh fixture IDs and logpoint/CDP/Node-inspector overhead are
confounders. This single group cannot establish an Edge/platform cause or
that observation cured anything. No unobserved historical callback, context
or protocol return is inferred from these successful calls.

**Evidence ceiling:** the actual healthy return chain is now captured and
version-bound, but the original fifth failed call still has no such trace.
The next minimum proposition, on a separately authorized recurrence, is to
identify the first unreturned boundary among native scheduling/callback,
check/Promise settlement, context destruction, protocol reply and Node
continuation using this call-bound observer. There is no additional launch,
environment workaround, product fix or natural acceptance inferred here.

### Separate observer correction, local gates and retained domains

After all owned processes exited, a new unit counterexample showed that the
observer's error payload `{phase, error}` could overwrite `condition-error`
with the attempted boundary name. The controlled test failed with actual
`resolve` versus expected `condition-error`; a one-field change to `failedPhase`
fixed it. This is an observer reporting defect, not evidence about historical
Login. The exact red, the final **160/160 Node PASS**, changed-file hooks and
separate commit are retained. The earlier e15 Node **159/159**, installed-source
preflight and hygiene PASS remain separate executions. No broad gate was
made green by changing a baseline, golden, xfail or skip.

`current-inputs.json` proves the only post-group harness differences are that
error-field name and its negative test, with committed bytes matching the
green unit run. It explicitly records **whole-harness equivalence false** and
**App rerun false**. All ten e15 raw traces were checked for error fields;
none occurred. They remain e15 diagnostic evidence, not fa8 App validation.

`domain-input-equivalence.json` checks all eight retained wheel/sdist archives
and changed paths. Package, build, lock and Python production coverage inputs
remain equal to **cc0bb3a3ec83bca6932a431dc766bb1713749050**; browser CJS is outside
those archive inputs. Native scope remains **48affef7e0504f63286793c571f6167c3fa82d69**
Gate 2 **3/3**, not a new Desktop or clean-VM execution. New Linux, build,
clean-wheel, coverage, Desktop and Quality runs are NOT RUN at this diagnostic
checkpoint. Prior Quality **35816144107** is still cc0's actual **13 success /
7 failure**, not e15/fa8 execution. Windows 99 nodes, kotaemon 4 capability
nodes and full Win32 mypy remain separately retained. Fixed original Dev is
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`; security policies and gates are unchanged.

Entry and every before/after-App comparison preserved all 135 raw protected
files, NUL, three post-incident configuration hashes, real database metadata,
98,853 canonical-environment entries and current cache count 610. Launcher
and App isolation were active before business imports; resolved config/data/
cache/settings/database/temp and native browser paths were inside owned roots.
All ten request/producer exits, idle worker project frames, process exits and
root removals are recorded separately; no process was force-terminated. This
Python audit boundary is not an OS sandbox. Historical writer **UNKNOWN**,
original config bytes **UNVERIFIED**, and cache **614 to 610 OPEN** remain;
there was no new clue, repeated historical scan, restore, mtime edit or real
cache cleanup. No total protection PASS or author risk acceptance is claimed.

The final report-only commit has its own input-equivalence, secret-scan,
protection and ordinary-push receipts in A's `final-delivery.json`. The five
historical refused-cleanup directories remain. Only explicitly named files
are staged; no branch/worktree, force push, merge, deployment or release.

## Retained bounded-acceptance failure at d84b3eab

The following natural-profile batch belongs to e8a14793 / harness 79a3f36e,
before the current diagnostic group. Its fifth failure and all unexecuted
successors remain unchanged; it is not replaced by either diagnostic arm.

### Frozen natural profile and actual exit results

`acceptance-plan.json` and `frozen-inputs.json` were written before the first
App. Both `MARA_BROWSER_FRAME_DIAGNOSTIC` and the legacy
`MARA_BROWSER_LOGIN_DIAGNOSTIC` were fixed at **0**. The latter was absent in
the original retained 37-scenario environment. Normal business observers and
all required scenario counterexamples remain enabled; no active Login CDP/rAF
observer, flush gate or deep Gradio logpoint was added to the exit probes.
`DEBUG=pw:api,pw:browser` records action and launch logs. The same switches were
used for all five cases, with the preregistered release-fault flag only on the
last case.

The 132-entry source/test/harness hash map, protected working bytes, dependency
inputs, runner scripts and runtime files were pinned. Every launch used the
same installed Gradio **4.39.0**, Playwright **1.61.1**, headless Edge
**153.0.4234.48** and normalized launch arguments. Browser executable and
adapter hashes match before and after execution. Each serial App had a fresh
owned runtime/profile/cache and exclusive port 8768. Launcher and App isolation
receipts prove the boundary was active before business imports; actual
config/data/cache/settings/database/temp and browser paths remain inside the
owned roots. This Python audit boundary is not an OS sandbox.

| Exit case       | Held/fault boundary                                                    | Outer / Node / App exit | Result                           |
| --------------- | ---------------------------------------------------------------------- | ----------------------- | -------------------------------- |
| Normal          | Actual Login, source and held generator reached                        | 0 / 0 / 0               | PASS                             |
| Assertion       | Held generator, then exact `owned actual` / `owned expected` assertion | 1 / 1 / 0               | PASS                             |
| Node watchdog   | Held generator and `watchdog-node`; `Node watchdog` primary            | 1 / 1 / 0               | PASS                             |
| App watchdog    | Held generator and `watchdog-app`; `App watchdog` primary              | 1 / 1 / 1               | PASS                             |
| Release failure | Login timed out; held generator never started                          | 1 / 1 / 1               | FAIL, not an expected-fault pass |

`five-exit-contracts.json` verifies the four actual held/fault boundaries using
their session/request/event identities. It separates UI/model/embedding
release, generator completion, terminal requests, idle worker project frames,
process exit and directory removal. All five Apps/Nodes and sampled browser
processes exited without forced termination; both owned roots per case were
removed. These cleanup facts do not turn the fifth functional failure into a
pass. No 5/5 verified marker was produced.

### New failure: exact timing, cleanup and evidence limit

`bounded-exit-release-failure.log` and `bounded-acceptance-blocker.json` retain
the natural failed attempt. The normal mouse Login click began at
**2026-09-26 12:20:49.295 UTC** (20:20:49.295 Beijing time); at
**12:21:19.302 UTC** it failed at
`tests/browser/chat_submission.cjs:136` after the original **30,000 ms** wait
for the element to be visible, enabled and stable. The Locator resolved the
Login button, but the click did not complete. No business queue request,
backend operation, conversation or generator is recorded; corresponding
fn/event/session/conversation identities are unavailable, not fabricated.

The original failure was saved before the harness's existing post-failure
observations. A current-main rAF request then lost its 2-second timer race.
The subsequent DOM snapshot was complete/visible/focused, with button rectangle
`(568, 315.375, 464, 40)`, opacity 1 and no reported animations. This is a
single **post-failure** snapshot, not proof that geometry stayed stable during
the click. Screenshot capture then timed out after 3 seconds, after fonts
loaded; it remains a secondary error. Browser GPU messages at 12:21:24.508 UTC
occurred during close, after both failures, and are not assigned as their cause.
No first-stall saved-native/utility-world/context lifecycle trace was captured
because the active observer was deliberately off.

The release-failure hook was armed before Login and fired during shutdown,
although its held-producer precondition had not been reached. Its UI release
error is retained separately in `producer-teardown.json`; model, embedding and
deletion-embedding release still ran. `model-gate-teardown.json` records
waiting/finished/wait-exited/generator-finished all false, and producer
before/after requests/generators/workers are empty. The Node Login primary
survives in `results.json`; `runner-cleanup-error.json` records App cleanup
failure without replacing that primary. An empty quiescent producer set is
not evidence that this held-exit contract passed.

Classification: a current natural Login actionability failure before the
business event chain, with root cause **UNPROVED**. Similarity to the older
Login stall does not prove a shared cause or a product/fixture classification.
The next single minimum proposition is whether the actual Playwright
utility-world stability check is waiting on an undelivered animation-frame
callback in the same document, rather than repeated unstable geometry or
context replacement. It requires correlated failed-state evidence; the
post-failure main-world probe is insufficient. No further App was launched
to pursue that proposition in this bounded acceptance round.

### Historical Login and verification scope remain separate

L retains five prior diagnostic App launches, all with Login completed, covering
only normal/intentional-assertion kinds. Four enabled the bounded frame observer;
one was its off control. They were not five exit-acceptance passes and did not
attribute or repair the historical fault. The user's statement that the old
desktop was visible and unlocked remains a statement, not an OS trace.
L's `login-frame-replay-bundle.zip` was rechecked read-only: **171 members**,
SHA-256 `7bb6841d4603273d4b452e13872066f6148fbb679e1196d04dcfd57af313d07e`.
It preserves 130 verified historical input entries; the old failing browser
binary identity remains UNRECORDED. No current version fills that gap.

The earlier **152 Node / 22 Python** passes, selector shared-flush and
card-before-choices evidence and their negative controls remain at their actual
recorded inputs. They were not rerun after this failed exit prerequisite and
are not substituted for a current full matrix. B's domain-equivalence receipt
proves e8a14793 differs from 79a3f36e only in this report and that all 132 raw
browser input hashes match. No observer or production fix is claimed this round.

Quality **35816144107** remains the prior **cc0bb3a3** execution with actual
**13 success / 7 failure**. New Quality, Linux, build/clean-wheel, coverage and
Desktop execution are NOT RUN here. B extends L's scoped input-equivalence
receipt: all eight cc0 wheel/sdist archives exclude the changed browser CJS
and report; package metadata/source/build/lock inputs remain equal. Native
Gate 2 remains **48affef7** 3/3, not a new current-tree run or clean-VM matrix.
No cc0 result is relabelled as 79a/e8 execution. The preregistered next Quality
baseline remains fixed original Dev `adab3f4d8f221e3620494fab0a24ef8e5557d12a`;
no dependency, baseline/alias, scan scope, required job or coverage floor changed.

### Forward protection and independent historical disposition

Entry and every before/after-App checkpoint match all **135 protected raw
files**, NUL, the preceding post-incident three-config hashes, both real
database metadata pairs, **98,853** canonical environment entries, **610**
current cache entries and the empty office-cache inventory. No new protection
difference occurred. Only task resources were released; the five historical
refused-cleanup directories remain. Config values/credentials and real
database/cache contents were not printed, restored or cleaned; mtime was not
changed. Final report delivery has its own protection and secret-scan receipts.

The separate historical disposition remains: configuration writer **UNKNOWN**,
original bytes **UNVERIFIED**, and **614 to 610 cache event OPEN**. The existing
bounded lookup found no old hashes/backups, prior per-entry inventory or writer
trace. There was no new clue and no repeated historical scan this round.
Metadata counts do not identify four lost user contents or normal eviction.
Forward isolation/comparison cannot establish historical integrity. The author
still needs to decide disposition of that uncertainty; this task does not
waive it or claim total protection PASS. Functional acceptance, historical
incident disposition and release security remain independent conclusions.

### Protection: separate historical uncertainty from forward isolation

| Domain                                   | Evidence and result                                                                                                                                                                                                                                                         | Status                                                |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Historical configuration writer          | The old three-file mtime overlaps an independent diagnostic but precedes its recorded cleanup. No historical writer trace exists; overlap and source capability are not attribution.                                                                                        | UNKNOWN                                               |
| Original configuration content           | No pre-change content hash or backup was found. Restricted local post-incident hashes are observations, not prior backups. No configuration values or credentials were printed.                                                                                             | UNVERIFIED                                            |
| Configuration post-incident observations | `.env`, `.env.example`, `flowsettings.py` match this round's first post-incident byte hashes and metadata. No restore or timestamp adjustment.                                                                                                                              | Current observation matches; historical incident OPEN |
| Real databases                           | Both known `sql.db` size/mtime pairs match; database contents were not opened for this comparison.                                                                                                                                                                          | Metadata unchanged; no new byte-integrity claim       |
| Real theflow cache                       | The earlier recorded comparison reports 614 to 610 metadata entries and a different metadata digest. Previous per-entry inventory is absent. Current metadata was preserved privately without reading cache contents. Timing, writer and content integrity remain unproved. | OPEN; no cleanup/restore                              |
| Canonical environment and office cache   | Existing metadata inventories match (98,853 canonical entries; empty `C:/Users/22826/office-cache` inventory).                                                                                                                                                              | Metadata unchanged                                    |
| User changes and retained roots          | All 135 protected raw files, NUL and historical refused-cleanup directories are retained. Final receipt separately verifies owned processes, port 8768 and staging.                                                                                                         | Per-domain receipt; no total protection PASS          |

`dbaefa8f` retains isolation red cases. `91a7f4aa` uses the existing process
runtime to check immutable owned roots/markers before business imports and
child execution, validate config/data/cache/settings/database/temp paths,
pin owned CWD and native browser profile/cache paths, and refuse Python I/O
after environment identity loss or teardown. Initial Chroma access to the
repository `.env` was refused before reading; the owned CWD correction is
recorded. This refusal is not evidence of the historical configuration writer.
The Python audit boundary is not an OS sandbox for arbitrary native I/O.

The fresh-process counterexamples cover missing/changed markers, wrong roots,
early imports, escaped settings/HOME, late workers, cleanup failures and lost
child environments. Negative results establish refusal before fake-user
access. Node independently rejects escaped roots/junctions before Playwright
loads. Five real-App exit probes passed on the recorded `isolation-stable-exit`
input map, including assertion, Node/App watchdog and release failure. Barrier,
model wait, generator, request, worker/process and root-removal states are
separate receipts. Earlier probes that only failed at login were reclassified;
their exit-code-only success summary remains retained and invalid.

The CI regressions were reproduced and repaired separately:
`48affef7` keeps diagnostic restoration keys out of the legacy path-key contract
and makes the normal child probe import its explicit repository path with no
`PYTHONPATH` dependency. `5dbcbc3a` requires a concrete database path in the
resolved-path receipt. `cc0bb3a3` subsequently fixes coverage atexit output in
the isolated test probes: only the data-file destination moves to owned
retained evidence; after process exit, the parent publishes byte-identical
unique fragments back to the original collector. The original filters,
aliases, subprocess patch and floors are unchanged. The controlled red/green
verifies 15 child fragments including 109 measured runtime-bootstrap lines.
The guard is not weakened to permit late runtime writes.

The prior five-App-probe harness is not byte-identical
to this final harness; those successes are not relabelled as new execution.

### Selector: exact last writer, minimal fix and remaining browser prerequisite

The installed and served Gradio 4.39.0 bundle hashes, dynamically resolved
component/function identities, queue event/session/actor, transport, guard
inputs/results, queued updates, assignments, Dropdown normalization and
actual flush boundaries are retained. IDs observed in a trace are not test
constants. A controlled scheduler gate holds only the actual Gradio component
flush; it does not alter guard results, serialize the App or force mouse clicks.

The real-App red at `8ea619f6` records session `6708az2vt55`, card event
`7e3eb8269c5847d48ee94c4ad6a7972b` and initialization event
`3d1629000b6f4f76a98663dbd872a209`. In flush 42, sequence 409 assigns
`["r3c-browser-owner-text"]`, then sequence 412 assigns the old initialization's
`[]`; the next exact backend scope is empty. Both guards captured the pre-flush
selection. Dropdown was not the final writer. This establishes a controlled
production defect, not the unique historical fd44 cause: the original failed
confirmation did not record that assignment trace.

The separate `7f29ce87` production commit changes only
`file_browser_refresh.js` and `file_browser_updates.py`. Existing card capture
records its index. An unchanged selector read omits its stale value assignment
only for the current card intent and an authorized available ID; choices still
apply. Revocation/deletion pruning, explicit clear, other index, Group,
multi-selection and mode transitions retain their existing contracts. It does
not convert every empty array to skip, patch DOM classes, introduce a global
version system or change dependencies, schemas or permissions.

Both controlled real-App schedules pass: one actual shared flush, and card
value/mode before initial choices. Final selected IDs, four output slots,
ordered DOM, Focus/summary and the next exact request scope are checked.
Seven evidence negatives reject the archived red, later clearing, absent
observer, completion without application, three slots, wrong DOM ID and wrong
session. `verification-input-scope-final.json` proves selector production and browser
observer bytes unchanged in the final source; it explicitly rejects equivalence
of the complete harness after the three isolation-related input changes.

Before any full matrix, `candidate-exit` on `79c99ae6` stopped at its second
case: normal exit reached the held producer and passed; the assertion case
failed while clicking Login, before the held boundary. Remaining Node/App
watchdog and release-failure cases are NOT RUN on that candidate. Both launched
Apps/Nodes exited, producers were quiescent and owned roots were removed.
This is not an expected assertion-pass or a selector failure.

`candidate-frame-blocker-analysis.json` records 100 identical button rectangles,
visible/focused/enabled state, no button animations and 334 advancing timer
ticks, while an explicit animation-frame callback did not complete in two
seconds. Screenshot failure is secondary; the original stability-wait error
is preserved. A separate plain-page frame probe passed and does not establish
the real-App failure's cause. No forced click, Enter substitution, repeated
click, enlarged timeout or full-batch retry was used to hide it.

The current follow-up observations and remaining failed-state proposition are
recorded above; this historical candidate failure is not rewritten.

### Retained verification and delivery scope at cc0bb3a3

At that prior checkpoint, focused Python: **22 passed**; Node guard/observer/frontend contracts:
**146 passed**. A first focused run overlapped a line-ending formatter and is
excluded from frozen verification; after formatting, the suite ran serially
and its input hashes were checked. Linux-platform mypy passes **1,982 files**.
Win32 mypy retains **15 identical error nodes/messages in 6 files**. The old
Windows 99 failures and separate kotaemon 4 capability failures remain their
original executions/comparisons; those large local suites were not rerun here.
Hooks, full Ruff, hygiene, lock parity, supply-chain policy, exact G0 controls
and secret scans use unchanged policies; final report delivery has its own
secret scan and input-equivalence receipt.

Retained Quality [35816144107](https://github.com/262412/MARA/actions/runs/35816144107) at `cc0bb3a3ec83bca6932a431dc766bb1713749050`
completed **failure** with **13 success /
7 failure** (actual job results below). All non-security
gates passed. Three Python audits and three container baselines fail; the
required aggregate remains failed. No security gate was waived or widened.

| Retained job                                               | Result  | Job ID         |
| ---------------------------------------------------------- | ------- | -------------- |
| Frontend and browser security                              | success | `107037967962` |
| ktem isolated runtime                                      | success | `107037968061` |
| Static, hygiene, and baseline ratchet                      | success | `107037968097` |
| Four clean wheel installations                             | success | `107037968103` |
| Coverage floors and production diff                        | success | `107037968107` |
| slide_cli                                                  | success | `107037968118` |
| Container lite supply chain                                | failure | `107037968123` |
| kotaemon Python 3.11                                       | success | `107037968124` |
| Container ollama supply chain                              | failure | `107037968128` |
| Repository and image secret scans / Repository and history | success | `107037968131` |
| kotaemon Python 3.10                                       | success | `107037968149` |
| Dependency audit root-py310                                | failure | `107037968159` |
| Dependency audit root-py311                                | failure | `107037968173` |
| Benchmark and root contracts                               | success | `107037968178` |
| Dependency audit container-py310                           | failure | `107037968209` |
| Container full supply chain                                | failure | `107037968216` |
| Python distribution supply chain                           | success | `107037968261` |
| Repository and image secret scans / Built image            | success | `107037968327` |
| Unified pytest collection                                  | success | `107037969107` |
| Required quality gates                                     | failure | `107048743912` |

| Retained Linux suite         | Result                                                   |
| ---------------------------- | -------------------------------------------------------- |
| ktem isolated runtime        | 3964 passed, 139 warnings in 638.33s (0:10:38)           |
| slide_cli                    | 147 passed (pytest -qq progress; exit 0)                 |
| kotaemon Python 3.11         | 422 passed, 10 skipped, 93 warnings in 179.77s (0:02:59) |
| kotaemon Python 3.10         | 422 passed, 10 skipped, 93 warnings in 150.23s (0:02:30) |
| Benchmark and root contracts | 1653 passed, 8 warnings in 560.97s (0:09:20)             |

Frontend CI has 40 Node tests and 8 browser security/preview smoke passes.
Those smoke scenarios do not replace the full 37-scenario App matrix.
The local 146-test Node execution is separately recorded in E.

Python audit blocking-key counts are root-py310: 14, root-py311: 14, container-py310: 14. Container keys outside
the frozen baseline are lite: 4, full: 4, ollama: 4: AnyIO plus three PCRE2 findings in
each target. Keys match the previous reviewed scan; this is not a claim of
security acceptance. PCRE2 package/layer records also match. The container
build/provenance/runtime-smoke stages pass; SPDX/CycloneDX image SBOM stages
are skipped after baseline failure, so no new image SBOM success is claimed.
Python distribution SBOMs are separate successful artifacts.

Retired Quality [35814242137](https://github.com/262412/MARA/actions/runs/35814242137)
at `79c99ae6` remains **10 success / 10 failure**: its root, static and
coverage regressions are retained with the subsequent controlled fixes.
Its incomplete coverage artifact has 74 members and no combined report;
it is not substituted for current coverage. No repeated CI was dispatched
for unchanged `40b187d9` or the retired SHA.

All four packages were rebuilt at cc0bb3a3 as eight wheel/sdist
archives and passed the existing clean-wheel gate outside the checkout,
including installed callback resources and `MARA`/`MARA-cli` entrypoints
without `PYTHONPATH`. Artifact `10732160259` has SHA-256
`2a83b542e32e375deae5dd8e764ab6e3bd03f1076abd7cde59baeb75e5139b74`. Local inspection verifies source members,
provenance and distribution SBOMs. CI artifacts represent the committed tree;
the 135 local protected modifications were neither staged nor included in it.
No new full installed CLI or source-Sidecar business-flow matrix is claimed
here; their prior source-bound R6-A evidence remains retained. New native
Sidecar smoke belongs to Desktop Gate 2 below.

Retained cc0bb3a3 coverage artifact `10732956317` has SHA-256
`ae06f718f4b27b94a1ff3de8f9f57db5755493951266913f204620fc2a973ea3`. The original collector, subprocess patch,
aliases, production scope and floors are unchanged; there are no temporary
runtime-file entries or raw package-relative aliases in the combined report.
The CI-configured comparison against `origin/main` passed at 3178/3345
statements (95.01%); the fixed original Dev comparison is independently
recomputed from this same artifact below.

| Package   | Covered/statements | Coverage | Original floor |
| --------- | ------------------ | -------- | -------------- |
| benchmark | 17146/19005        | 90.2184% | 90%            |
| slide_cli | 2293/2853          | 80.3715% | 70%            |
| kotaemon  | 7833/11012         | 71.1315% | 60%            |
| ktem      | 43721/51906        | 84.2311% | 50%            |

| Production diff                            | Covered/changed statements | Coverage                  | Original floor |
| ------------------------------------------ | -------------------------- | ------------------------- | -------------- |
| fixed_dev (`adab3f4d`)                     | 2420/2511                  | 96.3759%                  | 90%            |
| r6a_increment (`3b210087`)                 | 269/276                    | 97.4638%                  | 90%            |
| u1_increment (`32252dc0`)                  | 25/25                      | 100.0000%                 | 90%            |
| protection_selector_increment (`4721872a`) | 0/0                        | N/A (empty measured diff) | 90%            |

The protection/selector increment is **0/0, N/A**, not a claimed 100% result.
The JavaScript guard and changed Python binding lines add no measured changed
statements to the original Python diff collector. Their controlled browser
and Node evidence remains separate; the collector scope was not expanded.

R5-A/B/C and the retained U1 production modules are present in the inspected
report. The original production collector does not include desktop Sidecar
server modules; that scope was not broadened or represented as covered.
Coverage success does not close the missing browser/protection contracts.

Desktop Gate 2 [35815532063](https://github.com/262412/MARA/actions/runs/35815532063)
completed **3/3 success** at `48affef7e0504f63286793c571f6167c3fa82d69`:
Windows package/smoke/Defender, Ubuntu 22.04 package/smoke, and the same 22.04
package on Ubuntu 24.04. Original `eb6e4d83` 3/3 evidence remains retained.
`native-current-input-equivalence.json` proves that the final `cc0bb3a3`
diff contains only `tests/test_runtime_process_guard.py`; all native source,
package/build trees and locks are identical. This is scoped reuse of the new
48aff native execution, not a second native run at cc0bb. Actual logs and
small smoke/metrics/Defender artifacts are locally retained with digest checks.
It does not certify all clean VMs or the unexecuted 37-scenario Web matrix.

| Owner                | Contract                                                                         | Current evidence/status                                                                    |
| -------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| R5-A                 | Existing file-deletion coordinator and ordered external-store cleanup            | ACCEPTED; historical fault matrix retained                                                 |
| R5-B / L1-I1 / W1-W2 | Writer/ZIP, source mutation lifetime, event identity and stale-output boundaries | ACCEPTED within reviewed scope; retained code and counterexamples                          |
| C1                   | Graph cache publication/lifetime and authorization                               | ACCEPTED; no graph/cache algorithm rework                                                  |
| C2                   | Notebook/session short-transaction coordination and artifact registration        | ACCEPTED; no persistence policy change                                                     |
| C3                   | DownloadWorkspace, FD/manifest, transfers and retention                          | ACCEPTED; download lifetime belongs here, not R5-A                                         |
| R6-A / U1            | Inspection/identity/CLI/Sidecar plus direct browser tail/selection seams         | Implemented work retained; overall BLOCKED pending required browser and protection closure |

Preceding checkpoint baseline: `4721872a81cdf504f5c01de41ac134f76043dc8f`; accepted R5:
`41274852f1fda541b3162d5ae39a43beb8e92605`; fixed original Dev:
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`.
The commit ledger retains `dbaefa8f` (isolation red), `91a7f4aa` (test boundary),
`8ea619f6` (selector red/observer), `7f29ce87` (production fix), `79c99ae6`
(checkpoint), `5dbcbc3a` (typed receipt), `48affef7` (test portability), and
`cc0bb3a3` (owned coverage publication).
Retained full Quality/package CI input is the full `cc0bb3a3` SHA above.
Current observer/test source is fa8d8a27; the real-App diagnostic source was
e15a500d. Neither has new full Quality evidence. Scoped package/coverage/native
reuse is extended by A's domain-input-equivalence receipt.
Current report/local/remote identities are recorded in A's `final-delivery.json`;
B, L and E retain their own `final-delivery.json` identities and
ordinary-push receipt; report-only reuse verifies source/harness bytes and
all eight distribution member lists, and does not claim a new CI execution.

There is **no total protection PASS and no ACCEPTED R6-A result**. Stop at the
R6-A/U1 independent review point. The historical evidence below remains intact.

## Retained recovery checkpoint at 4721872a

The following recovery results and their “current” labels refer to that earlier
checkpoint and its stated SHAs, not new execution of the final source above.

### Recovery, exact tail and fixture exit

`recovery-checkpoint.json` recovers real exit codes, input hashes, logs and
sampled process identities. No historical launch PID was invented where the
old launcher did not journal it. At recovery no owned App/Node/browser or 8768
listener remained. The isolated f2 rename task actually exited 0 after 137.81 s;
it was not presumed killed from the interruption message. The f2 controlled
batch separately retains three completed passes, the rename endpoint failure,
focus interruption by the 600-second Node watchdog and three NOT RUN, with
partial evidence and no final results file. The invalid initial scenario
selector remains an exit-1, zero-scenario attempt.

The later controlled rename failure has exact root 70, last backend 83 and JS
tail 84: session `6pdb120yn3s`, B `a2daeb17ed29406c8388940855d83fec`, root event
`9984620b4e0a441bb804f713c8f175a7`, last backend
`304989ff8e544ab8bbf681722cf8b171`. Its actual JS result arrived after
**31.4447 s**, beyond the old 30-second test endpoint. `endpoint-budget-plan.json`
predeclared 45 s for this operation predicate only; model, barrier, SDK, App
and Node budgets were not enlarged. This explains that controlled failure,
not the uniquely unobserved cause of the original 4fb/322 accident.

`ended()` now requires the unique root and required successor requests,
matching session/conversation, terminal transport, active observer window and
actual final JS result. Missing logs, database commits or `settled()` snapshots
cannot satisfy it. Setup waits for the new-conversation operation's exact
endpoint before proceeding. Original concurrency pressure is retained. Tests
reject wrong UUID/session/request, absent backend/JS, disabled observer,
ambiguous branches, wrong IDs/order and three-output substitutions.

The f2 explicit model release remains. Fixture teardown independently attempts
UI, model, embedding and deletion releases; `held_finished` means model wait
exit only. Generator, requests, physical queue, workers/writers, process exits
and root cleanup are separate evidence. Only an owned suspended iterator is
closed after its requests/workers are idle. A failed monitor or nonquiescent
producer retains the root before store owners unwind. Primary failures survive
secondary release/close failures. Exact observed queued-event cancellation is
recorded without rewriting Gradio analytics; missing/wrong-session/processing
receipts and an active worker remain negative controls. The historical absent
queue entry alone was not retroactively declared proof of `clean_events`.

At fd44, controlled cases are **10/10** and real-App exit probes are **5/5
expected outcomes**: normal 0; assertion, Node watchdog, App watchdog and
release failure each 1. All five establish quiescence, stopped owned processes
and safe root removal. The held model remains unreleased/processing at
46.015 s before explicit release. These receipts precede the full matrix;
they are not newly executed results for the later diagnostic harness.

### Failed confirmation and bounded follow-up

| Fixture   | fd44 primary | fd44 required confirmation    |
| --------- | ------------ | ----------------------------- |
| retained  | 12/12        | 12/12                         |
| refresh   | 11/11        | 4 passed, 1 failed, 6 NOT RUN |
| seams     | 7/7          | NOT RUN                       |
| indexing  | 4/4          | NOT RUN                       |
| lifecycle | 1/1          | NOT RUN                       |
| public    | 2/2          | NOT RUN                       |

Each executed fixture used an empty owned runtime/cache, exclusive port 8768,
serial real App launch and the locked installed Gradio 4.39.0 frontend. All
executed fixtures have matching frozen inputs, actual Node/App exits,
quiescent producers and root removal. Primary exact B selection was observed
before A release: session `mj2tccx1n6r`, B
`19898f2bbdc240d5980e35a5d93d52f2`, event
`1def3dc11a5f4013b22b7770aca0c48b`. The primary proves authorized IDs, four
outputs, Focus/summary, messages/citations and old-result rejection for that
batch. It does not rescue the failed confirmation.

The failure is `selectorInitializationSelectionOverlap` at
`file_browser_concurrency.cjs`'s selected-class assertion (original line 163).
Session `mwe34r3rndl` has successful `select_chat_file` events
`4620db4d74c6465a9f382688ea1b941d` and
`ed29d3e6f053463a9f4fc075db53e9ef`, yet the text card remains unselected and
the observed refresh uses `selected=[]`. The old observer did not record
`applyFileSelection`/`applySelector` or selected-component assignments. This
is not proof of a fixture defect, framework suppression or product overwrite.
Cleanup passed separately. `failed-confirmation-checkpoint.json` preserves the
complete counts and original results digests.

Follow-up adds task-data-only input, guard, transport, component-value/choices
and DOM observation. Three separate focused diagnostics pass: the natural
isolated click; both initial selector returns held past a real click; and one
release of held selector/card transport. The second request is the normal
empty hidden-input reset in the observed isolated path. The aligned transport
case still applied the guards **163.7 ms apart**, so it does not prove the
same-frontend-flush case. Its pass does not identify the historical cause.
One preceding diagnostic failed syntax validation before any scenario; that
zero-scenario failure and its corrective commit are retained. No production
guard change was made on this incomplete causal evidence.

Next smallest proposition: determine the last writer of selected component
40 during one real click, correlating selection fn 127, selector fn 139,
mode/visibility fn 140 and Dropdown reconciliation in the same actual frontend
flush. Establish whether an older `[]` input can commit after the latest
authorized card value. Capture a deterministic failing event/assignment trace
before a minimal production fix. No forced click, API selection, global retry,
golden refresh or skip/xfail was used. See `selection-blocker-analysis.json`.

### Ownership, local gates and platform scope

| Scope                           | Owner / contract                                                     | Status                                                                      |
| ------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| R5-A                            | Existing deletion coordinator; ordered external-store cleanup        | ACCEPTED; historical fault matrix retained                                  |
| R5-B; L1/I1; W1/W2              | Writer/iterator/ZIP, Source leases/identity, browser/group contracts | ACCEPTED; original same-source double 36/36 retained                        |
| C1                              | Graph cache I/O/publication and authorization lifetime               | ACCEPTED; no algorithm/cache cleanup change                                 |
| C2                              | Notebook/artifact conversion and short Session commits               | ACCEPTED; no permission, copy/serialization or cross-store semantics change |
| C3                              | DownloadWorkspace, manifest/FD, transfer ownership and retention     | ACCEPTED; download lifetime belongs here, not R5-A                          |
| B1 / R5                         | Full App delivery plus independent production guard                  | ACCEPTED; original double 37/37 and all failures retained                   |
| R6-A inspection / CLI / Sidecar | Inspection extraction, identity fix, CLI actor, Windows parent pipe  | Implemented results retained; overall R6-A BLOCKED                          |
| R6-A/U1 recovery                | Test endpoint, producer/process exit and precise observations        | Controlled exit contracts pass; required full-browser confirmation failed   |
| R6-B/C/D and security upgrade   | Existing remaining matrix below                                      | NOT STARTED                                                                 |

This recovery changes only tests/observers/fixture/report. Prior U1 focus,
conversation readiness and scoped CSS production fixes remain. No architecture,
dependency, permission, schema, global concurrency or R5 lifecycle change.
Current small contracts: Python **18/18**, Node **142/142**, no skips. A test
ordering red (15 passed/1 failed) exposed Queue construction after a prior
`asyncio.run` had closed its loop; the test now creates and cleans the real
Gradio Queue on one running loop. This does not change production Queue code.

Windows affected suite: **99 failed, 4156 passed, 9 skipped, 135 warnings in 524.03s (0:08:44)**.
The same 99 nodes and failure nature remain against the original comparison;
no new/resolved nodes. Kotaemon separately: **4 failed, 405 passed, 23 skipped, 90 warnings in 120.52s (0:02:00)**;
the same four capability failures, no new/resolved nodes. Complete mypy with
Linux target modelling passes locally; Win32 modelling retains its exact
15 errors in six files. Native Linux CI is recorded independently below.
Ten static/hygiene/supply-chain/secret/G0 checks pass with unchanged locks,
baseline, aliases, scan scope, required jobs and coverage floors.

### Actual CI, packages and coverage

Recovered f2 [Quality 35734702856](https://github.com/262412/MARA/actions/runs/35734702856)
remains completed/failure, 13 success/7 failure; no redispatch. Frozen fd44
[Quality 35761447880](https://github.com/262412/MARA/actions/runs/35761447880)
is independently completed/failure, 13 success/7 failure, no nonsecurity
failures. Current 40b
[Quality 35766364808](https://github.com/262412/MARA/actions/runs/35766364808)
is **completed/failure**, actual
**13 success / 7 failure**.
All job logs and relevant artifacts are retained with digest/provenance checks.

| Native Linux test group      | Actual summary                                           |
| ---------------------------- | -------------------------------------------------------- |
| Benchmark and root contracts | 1650 passed, 8 warnings in 615.11s (0:10:15)             |
| ktem isolated runtime        | 3964 passed, 139 warnings in 697.17s (0:11:37)           |
| slide_cli                    | 147 passed (pytest -qq progress; exit 0)                 |
| kotaemon Python 3.10         | 422 passed, 10 skipped, 93 warnings in 176.26s (0:02:56) |
| kotaemon Python 3.11         | 422 passed, 10 skipped, 93 warnings in 177.75s (0:02:57) |

| Current job                                                | Actual result | Job ID         |
| ---------------------------------------------------------- | ------------- | -------------- |
| Benchmark and root contracts                               | success       | `106876814538` |
| Frontend and browser security                              | success       | `106876814835` |
| ktem isolated runtime                                      | success       | `106876814889` |
| Unified pytest collection                                  | success       | `106876815020` |
| slide_cli                                                  | success       | `106876815047` |
| Container lite supply chain                                | failure       | `106876815072` |
| Container ollama supply chain                              | failure       | `106876815079` |
| Static, hygiene, and baseline ratchet                      | success       | `106876815158` |
| Repository and image secret scans / Repository and history | success       | `106876815276` |
| Coverage floors and production diff                        | success       | `106876815295` |
| kotaemon Python 3.10                                       | success       | `106876815313` |
| kotaemon Python 3.11                                       | success       | `106876815320` |
| Python distribution supply chain                           | success       | `106876815386` |
| Four clean wheel installations                             | success       | `106876815493` |
| Container full supply chain                                | failure       | `106876815547` |
| Repository and image secret scans / Built image            | success       | `106876815590` |
| Dependency audit root-py310                                | failure       | `106876815967` |
| Dependency audit root-py311                                | failure       | `106876815993` |
| Dependency audit container-py310                           | failure       | `106876816026` |
| Required quality gates                                     | failure       | `106889220911` |

Current dependency blocking-key counts: root-py310: 14, root-py311: 14, container-py310: 14. No new/resolved keys
against the previous review. Each container retains four blocking keys,
including PCRE2, with no new blocking/raw keys; package/layer identity checks
remain separate from scanner-database differences. Container SBOM generation
was skipped after vulnerability failures. These failures stay blocking; S1 is
not waived by functional tests or coverage.

Current CI newly builds all four packages/eight archives and passes four clean
wheel installations. Eight-old-archive reuse was explicitly rejected: the root
sdist contains the changed `tests/test_web_operation_observer.py`; its newly
built bytes are verified against 40b. The local installed CLI/Sidecar business
flow remains attributed to **c1c7489ccc0911fcc8b950b47c59dcc479be449b**, with
unchanged implementation trees, entrypoints and wheel inputs, not a claimed
new local execution. Current CI uses the committed tree; protected uncommitted
user assets are not asserted identical to CI wheel bytes.

Desktop Gate2 remains the original **3/3** at
**eb6e4d8306ca9083819b7934568a4153727b4a3c**, run 35723190831. Its actual
Electron/PyInstaller input-scope proof excludes the later Gradio CSS change;
desktop sources, build configuration and locks remain unchanged. This is no
new native build, clean-VM sweep or unexecuted same-named pytest result.

| Coverage package | Covered / statements   | Unchanged floor |
| ---------------- | ---------------------- | --------------- |
| benchmark        | 17146/19005 = 90.2184% | 90%             |
| slide_cli        | 2293/2853 = 80.3715%   | 70%             |
| kotaemon         | 7833/11012 = 71.1315%  | 60%             |
| ktem             | 43721/51906 = 84.2311% | 50%             |

| Production diff | Fixed base                                 | Covered / changed lines |
| --------------- | ------------------------------------------ | ----------------------- |
| fixed_dev       | `adab3f4d8f221e3620494fab0a24ef8e5557d12a` | 2420/2511 = 96.3759%    |
| r6a_increment   | `3b210087ac057673b29af2b1777efeff82a0ecfb` | 269/276 = 97.4638%      |
| u1_increment    | `32252dc07f5ca70aaa9e9f6f142f5381488c3234` | 25/25 = 100.0000%       |

Recovery's new production increment is **0/0, N/A**, not a claimed 100% change.
The original collector, subprocess patch and normalized paths remain intact;
no temporary runtime files or raw aliases enter the report. Desktop Sidecar
files remain outside the pre-existing production coverage scope. Coverage and
Linux security smoke do not replace the required complete browser confirmation.

### Commit identities, preservation and stop

Recovery baseline: `f2cc1af366e33ddad74e89b75c6e586c19e6eba8`.
Accepted R5: `41274852f1fda541b3162d5ae39a43beb8e92605`.
Original Dev: `adab3f4d8f221e3620494fab0a24ef8e5557d12a`.
Full source/test/harness/package, report and remote identities are recorded in
the manifests and `recovery-commit-ledger.json`; the final ordinary-push receipt
records the actual report/local/remote SHA without a self-referential report hash.

| Commit     | Actual change                                                                 |
| ---------- | ----------------------------------------------------------------------------- |
| `e737b523` | docs: record R6-A interruption recovery checkpoint                            |
| `9fb35790` | test(web): expose fixture release and shutdown failures                       |
| `dbfefe1e` | test(web): drain owned browser fixtures and preserve primary failures         |
| `6cb44847` | test(web): reject unrelated or unobserved conversation endpoints              |
| `9492a29e` | test(web): characterize grouped file DOM and endpoint counterexamples         |
| `512d1372` | test(web): correlate conversation endpoints and preserve grouped DOM contract |
| `0a6a8221` | test(web): wait for the new-conversation endpoint after reload                |
| `242ced64` | test(web): expose unstarted queue cancellation at fixture exit                |
| `fd44f877` | test(web): record exact queued cancellation before fixture cleanup            |
| `f6dd0b56` | test(web): trace selector values and file selection application               |
| `63062e1c` | test(web): hold initial choices past a real file card selection               |
| `54e3db23` | test(web): correct late-selector diagnostic syntax                            |
| `561975f5` | test(browser): create and close Gradio queue on one running loop              |
| `40b187d9` | test(web): align owned selector and card transport delivery                   |

All 135 protected modifications retain their original bytes; NUL and all
historical retained roots are preserved. Final metadata matches all 98,853
canonical entries, 614 `.theflow` entries, the cache and both real databases.
The full five-file config/database comparison **failed**: `.env`, `.env.example`
and `flowsettings.py` under the real Cinnamon/Kotaemon configuration directory
have new mtimes at 2026-09-22 17:08:17 UTC, with unchanged sizes. Historical
snapshots have no content hashes, so unchanged bytes are **not established**.
The time overlaps an owned restore diagnostic but does not identify the writer.
`runtime-protection-difference.json` preserves the failed comparison and current
hashes. No configuration content was printed, overwritten or automatically
restored during this investigation. This protection difference remains OPEN
alongside the browser blocker; no blanket real-config-preservation claim is made.
No owned
App/Node/browser or port listener remains. Only explicit task paths were staged;
no branch/worktree, force push, merge, deployment, release, root cleanup or
environment sync occurred. No later unrelated tracked changes were found;
existing user edits were not reverted.

The report-only final commit reuses source/test/harness/package evidence only
after input equivalence is checked; report hooks and final secret scan still
run separately. Their actual receipts and the final protection/remote state
are retained beside this checkpoint. All previous 36/37, 11/12, interrupted,
invalid, failed and independently passing attempts remain historical evidence.
**Stop at R6-A/U1 with BLOCKED; do not report browser blocker closed.**

## Previous R6-A checkpoint at 32252dc0 (retained historical evidence)

Branch: `codex/r0-r1-safe-refactor`. R6-A baseline:
`3b210087ac057673b29af2b1777efeff82a0ecfb`. Independently accepted R5
source/tests: `41274852f1fda541b3162d5ae39a43beb8e92605`. Fixed original Dev:
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`.

**R6-A 整体收口 BLOCKED：完整浏览器矩阵 36/37，不报告限定验证通过。** Frozen source/test/package-input SHA:
**`4fb949279f69da427615ab70bb41867b171b9740`**. R6-A is **not ACCEPTED**.
The user's independent review now makes the agreed R5-C/B1 and R5 scopes
**ACCEPTED**. Earlier R1–R5-B, L1/I1 and W1/W2 acceptance remains unchanged.
All historical failures, fixes, same-source double 36/36 and double 37/37 evidence
remain retained. S1/PCRE2 are **OPEN**, G0's exact exception is unchanged, and
merge/release remain **NO-GO**. Stop at R6-A independent review; no R6-B/C/D
implementation, R5-D, dependency upgrade, merge, deployment or release.

Evidence parent: `D:/PythonProject/MARA-refactor-review-20260910-01a086ff/`.
`r6a-entrypoints/` retains characterization, red/fix, installation diagnostics,
commit/push receipts and the unchanged incoming report. `r6a-ci/` and
`r6a-final-ci/` retain the retired source runs. `r6a-final-verification/` retains
the failed 1d3b0457 browser batch and that source's Windows gates.
**`r6a-delivery-verification/`** and **`r6a-delivery-ci/`** contain the final
4fb94927 evidence. Previous `r5c-*` directories remain intact; the entire prior
R5-C/B1 report is also available at the baseline commit and in
`r6a-entrypoints/baseline-report.md`. The archived suffix below is byte-identical.

### Accepted R5 responsibility matrix

| Scope       | Owner and retained contract                                                                                                | Evidence and current status                                                                                                                                                               |
| ----------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R5-A        | Existing file-deletion coordinator and external-store cleanup; ordered failure/ownership boundaries                        | Historical deletion fault matrix retained; ACCEPTED within reviewed platform scope. DownloadWorkspace belongs to C3 below.                                                                |
| R5-B; L1/I1 | Ingestion writer/iterator/ZIP, Source leases and index identity                                                            | Writer cancellation/failure, delete/reindex and two-owner cases; original double 36/36 retained; ACCEPTED.                                                                                |
| W1/W2       | Browser operation observer and group event chain                                                                           | Identity counterexamples and close-before-list ordering retained; ACCEPTED.                                                                                                               |
| C1          | `knowledge_graph_cache` I/O; `knowledge_graph_lifetime` authorization and publication                                      | Atomic bytes plus current Source/Conversation snapshots; corrupt/partial/stale/ABA/session/source/reindex cases; graph algorithms and old patch methods retained; ACCEPTED.               |
| C2          | `_runtime_notebook`, `artifact_service`, Session service; `notebook_persistence` and `conversation_lifetime` short commits | Conversion/copy/ID/date/NotebookAccessError; independent Session/process races across both Notebook/chat write boundaries; owner-only writes and no cross-store rollback claim; ACCEPTED. |
| C3          | `DownloadWorkspace`, manifest/FD interfaces; `download_scope`, `download_http`, `artifact_transfers`; existing retention   | Producer ownership, authenticated HTTP claim, pinned FD/transfer lease, expiry/live-use exclusion and existing budgets; platform limits retained; ACCEPTED.                               |
| B1          | Full App chain plus independent production guard contract                                                                  | Event-specific Gradio 4.39.0 coalescing/delivery evidence, negative controls, final 41274852 double 37/37; prior 36/37 failure and NOT RUN confirmation retained; ACCEPTED.               |

R6-A changes none of those lifecycle implementations or Gradio registration/
timing boundaries. The accepted scope does not erase the recorded Windows
capability failures or authorize broader release acceptance.

### R6 remaining matrix, reusing the existing responsibility map

This matrix uses the retained R0 boundary map below, the Desktop
[feature matrix](../desktop/feature-parity-matrix.md), its linked Gate 2/3 evidence
and [release plan](../desktop/release-and-acceptance-plan.md). It is a status map,
not a new repository inventory or authorization to add Desktop features.

| Area                           | Implemented and verified evidence                                                                                                                                                                     | Implemented but unverified / conditional / not implemented                                                                                                                                                                                                                                 | Actual blocker and next review boundary                                                  |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| R6-A CLI / read inspection     | Shared doctor/files/sessions owner; legacy facade; both installed console aliases; identity negative cases; current wheel business flow and authenticated Sidecar HTTP                                | Full external-provider acceptance subprocess remains conditional on explicitly supplied provider/data; this round uses a real runtime with a local deterministic model endpoint                                                                                                            | BLOCKED by the current failed 37-record browser matrix; no independent acceptance        |
| Sidecar / Electron             | Existing shared application, IPC, task journal/SSE, cancellation/retry and schema contracts; historical Gate 2 Doctor/Files/Sessions Verified; current source/npm/native CI recorded separately below | Current Gate 3 has implemented indexing/query/session/model-route slices with automated evidence, but Windows 10/11 clean VM, native picker/OS drag, IME, secure storage/migration and full format/preview acceptance remain unverified                                                    | Gate 3 remains In progress. Current hosted package smoke does not re-certify product VMs |
| Desktop product parity         | Existing Notes/Studio/Graph and exports remain shared Web/CLI services                                                                                                                                | Desktop Notes/Studio/Graph/export/preview P0 and full Index/Reranking/MCP/user resources/settings are not completed as a whole; model/help/settings baseline pages are partial. Deep links/multiwindow and P1 updates/notifications remain optional/later according to the original matrix | No new Desktop feature or R6-B implementation in this round                              |
| MCP / agent adapters           | Existing `kotaemon` model/tool/agent/MCP modules, package/adapter contracts and installed command tree                                                                                                | Provider/tool-server integration, external credentials/network, Office/media converters and full agent/deck integration are conditional or not rerun here; unit substitutes do not establish live provider parity                                                                          | Preserve existing commands and ownership; no general DI/repository/MCP framework         |
| Artifact / deck                | R5 accepted artifact lifecycle; current CLI notes materialize→index→backfill and artifact generate→export→register→reload; existing deck command/alias/package tests                                  | Real Office/media export and visual/native “save as” acceptance remain format/tool/platform dependent; no new deck format or Desktop export feature                                                                                                                                        | No record deletion cascade into Source/shared blobs/history exports                      |
| Benchmark                      | Existing adapters, execution/planning and benchmark/root contract suite; fixed original Dev coverage comparison                                                                                       | This round is not a new performance/quality benchmark or validation of all external datasets/models; dataset, GPU/Slurm and provider availability are conditional                                                                                                                          | R6-C future review scope only; no metric or artifact-completeness claims from unit tests |
| Install / platform / resources | Four wheel+sdist builds, owned noneditable installation, outside-repository consoles, unchanged resource contracts and current clean-wheel/native CI                                                  | Full clean-VM installation/upgrade/uninstall, every platform integration and Windows restricted-FD/long-path contract are not universally verified                                                                                                                                         | Explicit platform limits below; no editable/PYTHONPATH/old-global-console substitution   |
| Full repository delivery       | Existing static/hygiene/lock/coverage/secret and supply-chain gates run on the new source                                                                                                             | Security/PCRE2 remediation and broader product delivery remain separate work                                                                                                                                                                                                               | S1/PCRE2 OPEN; required aggregate and merge/release NO-GO; no R6-D or security upgrade   |

### Actual boundary changes and retained entrypoints

The baseline-to-source range changes **15 files: 7 production and 8 test/fixture
files**. The sole new production module is
`libs/slide_cli/slide_cli/docqa_inspection.py` (456 lines). `docqa_runtime.py`
shrinks from 599 to 174 lines and remains the compatibility facade.
Inspection was not duplicated into the Sidecar or a generic repository layer.
The existing `docqa_import_capabilities` module remains its own owner;
`session_projection` is not an equivalent collector (different normalized
runtime semantics and bootstrap dependency).

The new owner has standard-library imports and function-local settings/SQL
imports. It has no Click, Gradio, complete Runtime/model-manager dependency,
subprocess acceptance runner or reverse import into the facade. Pure inspection
import does not bootstrap runtime settings, query/create a database or initialize
models. Calling a collector still performs the original bootstrap/schema/query
work; "read-only inspection" is not a promise that initial runtime bootstrap can
never create its own runtime schema. Parent `slide_cli` package exports still
import their existing PPTX/Pillow/NumPy dependencies; no zero-third-party-import
claim is made.

`structure-boundary-proof.json` verifies all **13 moved signatures**, and unchanged
ASTs for the five retained runtime functions: factory/profile setup, import
capability delegate, graph-context JSON parsing, acceptance JSON extraction and
acceptance subprocess. Click rendering, exit codes and acceptance-subprocess
ownership remain in their original modules. All old collector imports and actual
CLI/Sidecar monkeypatch consumers remain supported; old helper names remain
explicit facade aliases. New diagnostics for the three retained fallback handlers
log fixed debug messages, without values or credentials.

Characterization fixes field order/types, date ISO handling, JSON parsing and
copy semantics, graph source fallback/deduplication, user/model/index selection,
issues/warnings and exception timing. Persisted configured/default selection and
the existing admin fallback are unchanged; no admin is created by inspection.
`installed-provenance.json` checks all installed Python members against this
round's four wheels and proves the touched Click decorators/signatures unchanged.

### Three separate red-to-fix seams

1. **Missing identity inspection.** `9397153e` records the real owned database
   negative cases before extraction: an empty default principal removed the SQL
   filter, exposing another owner's private session in list/count/doctor paths.
   Red: 3 failed / 9 passed. `33c633df` applies the existing owner-or-public
   predicate even for the empty principal, matching RuntimeSessionService. No
   client-supplied `user_id`, new administrator, policy/schema/ID migration or
   fake healthy status. A configured legitimate user still sees owned/public
   rows. A missing managed identity is diagnosed, public reads remain allowed,
   private records remain excluded. Legacy blank-owner data semantics are not
   migrated. `2948d992` then performs the structural extraction separately.

2. **Actual CLI Notebook/artifact actor.** Installed note/artifact validation
   exposed missing required `user_id` arguments. `3dee74e9` records 10 real-DB
   non-admin command failures; `e4b0e592` explicitly forwards `runtime.user_id`
   at all 24 directly participating caller boundaries, including internal
   artifact helpers. Service signatures, normalize/merge, short commits,
   NotebookAccessError and public-session-versus-Notebook-write policy remain
   unchanged. The focused repaired set passed 25 tests. Real installed notes
   and artifact export now reach the existing services and survive reload.

3. **Windows Sidecar cold import while parent stdin remains open.** Real
   authenticated HTTP inspection hung while importing native dependencies;
   direct NumPy and worker imports without a pending parent-pipe read completed.
   Owned diagnostics separately reproduced the conflict with `os.read`, buffered
   read, duplicate FD and direct `ReadFile`. `16aa6d7d` records two red cases
   (with/without heartbeat); closing stdin in cleanup unblocked the child.
   `4fb94927` changes only the existing parent-pipe wait: Windows uses
   `PeekNamedPipe` and reads available bytes, with 50 ms idle polling; POSIX keeps
   its original read-until-EOF loop. The borrowed FD stays open, no model preload
   or debug endpoint is added, and EOF still shuts down the existing server.
   The exact native lock internals were not established. Microsoft
   [PeekNamedPipe](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe)
   and [ReadFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-readfile)
   API behavior informed this narrow fix. Final focused suite: 20 passed; real
   installed HTTP plus restart/parent-EOF scenarios passed.

Test-only corrections stay separate: `7e26b8f1` supplies explicit source paths to
two characterization subprocesses in Linux CI; installed-entry tests remove all
PYTHONPATH/PYTHONHOME/VIRTUAL_ENV overrides. `1d3b0457`'s attempted test-fixture
bootstrap correction exposed shared module-state contamination in the full
Sidecar suite. `fa101355` instead mocks only the intended persisted-route
collaborator, and the complete suite passes. Both earlier fixture failures remain
recorded; no xfail/skip/golden update was used.

### Installed console and actual HTTP acceptance

The four wheels built at 4fb94927 were installed noneditable with no dependency
resync into `D:/MARA-s1-01a086ff/env`. All subprocesses run outside the repository,
including a Unicode/spaced cwd, using that environment's actual `MARA.exe` and
`MARA-cli.exe`. Provenance checks resolve their installed distribution files and
compare wheel hashes/member bytes. The canonical environment is untouched.
Local package inputs include the preserved user platform-asset modifications;
hosted CI builds clean tracked 4fb94927. These are separate recorded artifacts,
not a claim of identical complete wheel bytes.

`acceptance/passed.json`, `acceptance/receipts.json`, per-command stdout/stderr and
per-request HTTP JSON retain: **60 actual command nodes**, help through both
aliases, Bash completion/source, empty doctor exit 1, files/sessions JSON, valid
doctor readiness, Unicode input, index→simple/default-MARA QA→saved reload/resume,
notes add/list→materialize→index→backfill, source selection, artifact generation
and Markdown export→registration→reload, and final deletion. JSON validation
parses all stdout, not a trailing fragment. A missing path fails preflight before
indexing; a duplicate valid path yields one success plus one failure and exit 1.
Neither partial result is represented as a cross-storage rollback.

The Sidecar uses real authenticated loopback HTTP, actual application/Runtime
services and journals. The local deterministic endpoint substitutes only the
external model/embedding service. Evidence covers bearer 401, origin 403,
client-identity injection 422, private-session 404, whitelist/path redaction,
matching request headers/body IDs, no-store, task IDs, SSE and terminal states,
real indexing, session creation, query success, barrier-driven cancellation,
retry with a new task, reload after a real Sidecar restart and parent-EOF exit 0.
Files/sessions agree with the CLI under explicitly shared data/configuration.
CLI default MARA and desktop simple profiles remain distinct; route/reasoning/
origin defaults were not changed to force equality.

The separate `identity/` database contains another non-admin owner's private
and public sessions and no default/admin user. Both installed entrypoints see
only the public session, private detail is denied, identity injection is rejected
and doctor stays unhealthy with the identity issue. Legitimate user and
owner-only Notebook negative tests remain in the normal regression suite.

### Frozen-source verification and preserved failures

| Gate                         | Actual 4fb94927 result / evidence                                                                                                                                                                                                                                                                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Full original browser matrix | **FAILED: 36 passed / 1 failed of 37** on 4fb94927. Six fixtures; `complete-browser-matrix-failed.json`, `browser-action-blocker.json`, `browser-input-and-cleanup-proof.json`                                                                                                                                                                    |
| Web Node                     | 93 passed; `delivery-node.log`                                                                                                                                                                                                                                                                                                                    |
| Desktop npm verify           | TypeScript/schema drift, Electron Node 80, renderer 41, packaging 5; Sidecar 150 tests with 2 original skips; builds passed; `desktop-all-verification.log`                                                                                                                                                                                       |
| Full affected Windows        | 99 failed, 4141 passed, 9 skipped, 135 warnings in 565.82s (0:09:25); exact 99 retained failure nodes/nature, no new/resolved/changed failures                                                                                                                                                                                                    |
| Separate kotaemon Windows    | 4 failed, 405 passed, 23 skipped, 90 warnings in 131.41s (0:02:11); exact four FIFO/symlink nodes/nature, separately compared                                                                                                                                                                                                                     |
| Complete mypy                | Linux platform model: success, 1978 files. Windows model: same 15 platform-interface errors in 6 files; logs retain both results                                                                                                                                                                                                                  |
| Static/hygiene               | Scoped hooks, full Ruff, round/fixed-Dev/full hygiene, constraints, lock parity, supply-chain contracts, G0 negative controls and source secret scan passed; exact baselines unchanged                                                                                                                                                            |
| Four packages                | Four wheels plus four sdists built; all eight current CI artifact hashes, source members, SBOM/provenance verified; four clean-wheel installations passed                                                                                                                                                                                         |
| Quality CI                   | [35688057373](https://github.com/262412/MARA/actions/runs/35688057373): **13 success, 7 failure, 20 actual jobs**; no nonsecurity job failures. Overall `failure`                                                                                                                                                                                 |
| Native Desktop CI            | [35688402221](https://github.com/262412/MARA/actions/runs/35688402221): **3/3 success**, Windows native package/Defender, Ubuntu 22.04 native package, same Linux package on Ubuntu 24.04; real Renderer→Preload→IPC verified. Task-persistence fault/recovery smoke is evidenced on Windows and 22.04; no claim that the 24.04 subset repeats it |
| Coverage                     | All original package floors, fixed-Dev and round increment passed; verified current-source CI artifact, exact numbers below                                                                                                                                                                                                                       |

The two new parent-pipe pytest cases were executed on native Windows in the
20-test focused run. The existing Desktop workflow executes the 150-test
unittest suite on Windows/Linux, not those two pytest functions. Native Linux
package cold startup/HTTP and process lifecycle smokes provide separate POSIX
evidence; the unchanged POSIX branch's two named new pytest cases were not run
on Linux. No Linux result is inferred from a Windows platform-model run.

Only one complete original 37-record matrix is required on this frozen source:
six fresh owned fixtures, empty runtime/cache roots, exclusive fixed port 8768,
serial App starts and cleanup receipts. No Web timing/guard/harness assertions
were weakened and no mandatory double batch was newly imposed.

The final primary attempt passed its retained 12-record fixture, then failed
`conversationDuringFileRefresh` in the 11-record refresh fixture. The wrapper
stopped as planned. After one isolated diagnostic, only the 14 previously unrun
records were collected on the unchanged inputs: seams 7/7, indexing 4/4,
download 1/1 and public permissions 2/2. This completes the original failed
matrix's evidence; it is **not** a second acceptance, confirmation or assembly
of replacement green results. The final count remains 36/37. No complete retry
was launched.

The primary failure found the exact `R3D context B` option, but Playwright
reported instability and then detachment, reaching its original 30-second
click timeout. In session `zq6b0magy`, fn 117 / event
`dae5e64be4604280957e97b1711f6c6d` was A's held `.txt` refresh. Selection callback
order was A→B→A during setup; no final B selection callback or later B refresh
was observed. This locates the failed interaction before the intended final
switch contract and does not prove safety from missing logs. Product versus
fixture cause remains **unproven**. A single isolated diagnostic preserving
the actions/assertions/timeouts, with added DOM samples, queue payloads,
Playwright trace, screenshot and final DOM, passed. That diagnostic does not
replace the primary failure. Causal classification of the unstable/detached
option is the remaining browser blocker; no speculative Web event repair or
fixture relaxation is included in this CLI/Sidecar refactor.

Earlier attempts are not relabelled: 2948d992's retained browser sub-batch passed
12/12 but was retired after the Linux fixture failure, before the other 25
records. 1d3b0457's first browser batch had **11 passed / 1 failed of 12**; the
remaining 25 were not run. The 5-second rename setup predicate in
`lateConversationOperations` timed out; later callback/SQL evidence shows the
same conversation ID received the correct name, but the exact timing cause is
unproven. `retired-attempts.json` and raw DOM/backend/SQL evidence preserve this
failure. There is no cross-SHA/batch assembly of green results or blind retry of
that source to select a green result.

An installed diagnostic with a longer owned runtime path reached deletion and
failed in the disk stage: source path length 216, quarantine path length 261,
WinError 3. The Source row and blob remained; no external-store rollback is
claimed. Final acceptance uses a fresh shorter owned runtime root, retaining
Unicode input and the original path-security rules. This is a recorded Windows
long-path limitation, not a product path-safety relaxation.

Windows's 99 historical failures are compared by exact node, primary error and
assertion nature, separately from the kotaemon four. Categories remain secure
directory-FD capability (32), fchmod (23), symlink privilege (20), lifecycle lock
(10), invalid filename (3), held-file replace (2), long path (1), secure-FD
precopy (1), disabled artifact defaults (3), QASPER CRLF (1), PDF.js license CRLF
(1), protected skill text (1) and mode bits (1). Kotaemon has one FIFO/mkfifo and
three symlink-topology privilege failures. They are real unsupported/unverified
capabilities where the product needs them; historical status is not a waiver.
The Windows mypy interface errors are a separate result. No path-security
weakening, broad skip, dependency change or user-file normalization was used.

### Coverage, supply chain and delivery identity

| Scope         | Covered / statements | Percent  | Unchanged floor |
| ------------- | -------------------- | -------- | --------------- |
| benchmark     | 17146 / 19005        | 90.2184% | 90%             |
| slide_cli     | 2293 / 2853          | 80.3715% | 70%             |
| kotaemon      | 7833 / 11012         | 71.1315% | 60%             |
| ktem          | 43699 / 51886        | 84.2212% | 50%             |
| fixed_dev     | 2395 / 2486          | 96.3395% | 90%             |
| r6a_increment | 244 / 251            | 97.2112% | 90%             |

Current CI artifact ID **10677359420**, SHA-256 `85c64ba01c4d454fad8f7d19b2197c9eedc857195ad65edd66ac87d005d95a35`; raw SQLite, JSON, XML and configuration are retained. The artifact digest, subprocess patch, package floors, unchanged collector/aliases, fixed-Dev and R6-A increments were verified with the original gate code. No temporary runtime files or raw package-relative aliases are counted. Per-module summaries and uncovered lines remain in `coverage-verified.json`.

The existing production coverage scope includes the four original Python package
areas, not `apps/desktop`. Sidecar parent-pipe behavior is validated by its
focused real-process/HTTP and native workflow evidence, and is not silently
added to or omitted from a newly altered coverage denominator. Collectors,
subprocess coverage patch, aliases, package floors and 90% production-diff gate
remain unchanged.

Fresh dependency audits retain blocking keys (root-py310: 14, root-py311: 14, container-py310: 14); image scans retain blocking keys (full: 4, lite: 4, ollama: 4). Exact keys and advisory aliases are compared with the accepted 41274852 evidence, with no newly added or resolved blocking keys in this round. All remain blockers. The PCRE2 package/layer comparison is retained. Image build/runtime smokes passed; the security gate prevented image SBOM generation, so no image SBOM is claimed. Python package CycloneDX/SPDX/provenance for all eight archives was verified. No lock, baseline, alias, required-job, scan-scope or threshold change; S1/PCRE2 OPEN, merge/release NO-GO.

| Identity                                               | SHA / receipt                                                                                                                                                                                          |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Fixed original Dev                                     | `adab3f4d8f221e3620494fab0a24ef8e5557d12a`                                                                                                                                                             |
| User-accepted R5 source/tests                          | `41274852f1fda541b3162d5ae39a43beb8e92605`                                                                                                                                                             |
| R6-A baseline / preceding report                       | `3b210087ac057673b29af2b1777efeff82a0ecfb`                                                                                                                                                             |
| Inspection red → identity fix → extraction             | `9397153e623498211d26f55bbf7e0308fd52fbda` → `33c633df30cfe31686ae84fed9422d443f300911` → `2948d9922a4e57165e5d46821309d8d7a43f29b0`                                                                   |
| CLI actor red → fix                                    | `3dee74e9ad8e5c2f21e37c358578c269d7f73ae1` → `e4b0e592c1c4fd9ab77ebcbe4b1bd885dd6e6575`                                                                                                                |
| Test/fixture corrections                               | `7e26b8f1191c809fce4011945a84c62dc9996186`; retired `1d3b0457919325e77276e0417d8b7737b588ebfc`; corrected `fa1013557882fe2d40474a59640a278ad24f7c09`                                                   |
| Parent-pipe red → final fix/source/tests/package input | `16aa6d7d3c0a842e4b0c0465afc7b233a0f23449` → `4fb949279f69da427615ab70bb41867b171b9740`                                                                                                                |
| Report / final local / final remote                    | Exact full SHAs are in `r6a-delivery-verification/r6a-final-state.json` and `r6a-entrypoints/r6a-report-push.json`; the report-only commit follows frozen 4fb94927 without other tracked input changes |

All **135 protected raw file hashes** remain unchanged, including the two CRLF-only paths that can disappear from normalized Git diff. `NUL` remains 95 bytes, SHA-256 `bd28ac1693f0d94ea97696fed16879a2e2cfeecf19d350451f49224ba1955a3c`. The canonical environment (98,853 metadata entries), real theflow cache (614), office-cache (0), and five real config/database file metadata records match the round start. Three historically refused cleanup directories remain present. All six browser roots and the isolated diagnostic root were cleaned; failed installed/diagnostic evidence and owned historical runtime remnants remain preserved, with no root-wide cleanup. Final post-report metadata, exact paths/hashes, input equivalence, ordinary-push and secret-scan receipts accompany `r6a-final-state.json`.

The report-only commit changes no source/test/harness/package, workflow, lock,
baseline, alias, scan scope or required-job input. Its source-ancestor/input
equivalence and final committed-history secret scan are recorded explicitly;
report-only reuse is not a substitute for those checks. Only the named report is
staged, and ordinary push receipts identify the actual remote commit.

Work stops at **R6-A independent review**. R5 acceptance remains in force;
overall merge/release remains **NO-GO**.
The retired 2948d992 CI run `35685718084` ended cancelled: 11 success, 8 failure, 1 cancelled (including the repaired slide_cli subprocess fixture failure). The retired 1d3b0457 run `35687048837` ended cancelled: 12 success, 6 failure, 2 cancelled. Their final API snapshots and original logs remain retained; neither is used as the final coverage/source run. `retained-execution-index.json` indexes the R6 raw ledgers without rewriting failures.

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
