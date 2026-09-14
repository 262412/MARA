# MARA refactor status — 2026-09-14

## Current round: R3-D Web closeout

**R3-C: ACCEPTED**, following the user's independent review of
`0e90c86c0eb57136955aba2851f1c52328e45c42`. Accepted R1/R2/R3-A,
F1–F4 and R3-B remain accepted. Review base:
`29e489bf4b8ea668f06ab2348299fa2ae24256fd`; fixed original Dev:
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`.
The [accepted R3-C report](https://github.com/262412/MARA/blob/29e489bf4b8ea668f06ab2348299fa2ae24256fd/docs/development/refactor-status.md)
retains the earlier characterization, browser, coverage and security evidence.

**D1/D2/D3 限定功能验证通过；R3-D Web 功能范围收口，等待独立收口审查。**
**Overall stable-source CI: FAILURE. S1/PCRE2 remain open;
merge/release remains NO-GO.** The additional Gitleaks checksum false positive
is separately evidenced below and remains a failing required check. Neither
security nor desktop binary packaging is claimed as accepted.

Final source/test SHA: **`b553444086b0d4c060a36a9cf07d3bbde94d2904`**.
Production last changed at `dd4e3077d9a2ec7431aab10c19594f94092a0608`.
The last four commits change tests/observers only. The last two only repair
sequential file-table observation and barrier cleanup; production, Python tests
and build inputs equal `04a5f179` (`stable-source-equivalence.json`). The final
complete browser matrix and stable CI run use `b5534440`; local full Python
suites/builds use those identical inputs at `04a5f179`. Ordinary source push and
remote readback verify `b5534440` (`stable-source-push.json`). The later report-only
commit's actual report/local/remote SHAs and source equivalence are recorded in
`r3d-report-commit.json` and `r3d-final-state.json`.

| Ordered, reviewable change                                         | Commit                                     |
| ------------------------------------------------------------------ | ------------------------------------------ |
| D1: failing overlap tests on the old implementation                | `fb18465e1e342aa35a6a51a6ff16a8a7715603fc` |
| D1: retain browser intent across initialization/index refresh      | `4b8215c3a84645cccdd588bbd725d0c87d62e262` |
| D1: retain legacy event-spy adapters                               | `b807166fd7eb5d8fc4f8891b953a736878d3e80f` |
| D2: move unchanged callbacks to owned resources                    | `b049112817ecd254a2cfe61cee1ccde99795d18f` |
| D3 fix: resolve the actual indexed note result                     | `5ffcb584cd245b144a53f97cc48a5bf29c166266` |
| D3 fix: retain authorized groups and expand displayed members      | `29cc3d820b438a2aab04c1e7569831243afb1a6b` |
| D3 fix: reject late Studio presentation results                    | `f74f7f646b7f984574ad2948993e57462a1771bb` |
| D3 fix: restore authorized artifact cards                          | `e846bf458ad4fce51d9e4d6efd042af9e4c638d5` |
| D3 fix: consume the real selector mapping                          | `e1e98eb7c8c37c9f7cff939bfd176e68e063f90e` |
| D3 fix: retain actual chat history when generating a Mind Map      | `dd4e3077d9a2ec7431aab10c19594f94092a0608` |
| D3: complete App browser regressions                               | `852fbb42d389a5927b6a87f34897e088041ce0ef` |
| D3: precise preview-revocation observer and public artifact test   | `04a5f179a6278ec6af1a0bb2d3912a66e85b6d5a` |
| D3: observe the refreshed source ID after reindex                  | `1275486ec1ff5c0c00728d0bfdf5e060ddfdac67` |
| D3: wait for filtered rows and retain the original barrier failure | `b553444086b0d4c060a36a9cf07d3bbde94d2904` |

### D1: initialization and refresh ordering

The former remaining-scope startup overlap was reproduced before fixing it.
Controlled callback/delivery barriers showed an old initialization result
replacing a newer filter, reverse filter deliveries showing the wrong file type,
late selector initialization clearing a selection, old conversation refresh
restoring the wrong Focus, and late upload/card results replacing a newer source
choice. Evidence includes `d1-initial-baseline`,
`d1-filter-context-baseline-observed`, `d1-expanded-old-source`,
`d1-quick-upload-intent-red` and `d1-successive-source-observed`.
The A→B→A baseline already passed; it is retained as a regression, not claimed
as a reproduced defect.

`file_browser_updates.py` is a narrow Web result adapter. The existing authorized
callbacks still perform each query/index operation once with the real request.
`file_browser_refresh.js` owns per-document mount epochs, filter/view intent,
catalog changes, request issuance and upload intent. Final client application
checks the captured context against the current conversation/selection/filter;
late results cannot overwrite a later applied request or a newer user intent.
Filtering still changes presentation only. Upload and deletion effects run to
completion; only stale presentation/reset outputs are suppressed.

All file-library refresh registrations use that result boundary: initial
selector loads/sign-in subscriptions, filters, source choices/tags, conversation
changes, chat-tab selection, selector vocabulary changes, quick/full uploads and
index notifications. The old refresh/select methods and their four/three output
contracts remain. The previously unused `chat_file_rows` presentation output is
now hidden JSON so the browser can apply the four-result bundle together.
Old patchable callbacks are consumed by the adapters. Gradio 4.39's server-side
selector vocabulary is copied into its per-session component configuration;
a small selector-local lock covers only copy/assignment, never IO. No global
request, whole-site lock, retry loop or new generic state/DI framework is added.

The final 11 controlled-race scenarios cover initialization/filter overlap,
in-flight filtering, reverse delivery, A→B→A, selector initialization/selection,
conversation switching, file and URL uploads followed by a newer source choice,
delete notification/old refresh, successive cards, two same-user browsers and
a second authenticated user. They start the initialization races while the
original requests are held; no startup prewarming or repeat clicks are used.
The D1 focused set passed 27 Python contracts and 12 Node cases before D2;
legacy adapter regressions add 17 passes. Final complete suites include them.

### D2: callback ownership and packaged loading

Eight effective callback strings were frozen before extraction and retain exact
UTF-8 content, leading newlines and Gradio function-expression form. Old Python
names/patch entries still resolve them at module import, before the same event
registration/invocation positions. Index-manager focus aliases share the same
resource. No JS behavior, DOM token, iframe/CSP policy, authorization, CDN or
framework version was changed by the migration.

| Old callback name                | Unique resource under `ktem/assets/js/` | Actual caller/load position                                             |
| -------------------------------- | --------------------------------------- | ----------------------------------------------------------------------- |
| `chat_input_focus_js`            | `chat_input_focus.js`                   | Conversation/auxiliary events, App creation; index-upload focus aliases |
| `quick_urls_submit_js`           | `quick_urls_submit.js`                  | Auxiliary URL input callback                                            |
| `recommended_papers_js`          | `recommended_papers.js`                 | Recommended-paper preview event                                         |
| `clear_bot_message_selection_js` | `clear_bot_message_selection.js`        | Conversation selection tail                                             |
| `pdfview_js`                     | `pdfview.js`                            | Message, conversation, preview and auxiliary event chains               |
| `fetch_api_key_js`               | `fetch_api_key.js`                      | Existing demo App-load callback                                         |
| `scroll_answer_panel_js`         | `scroll_answer_panel.js`                | Message completion scroll node                                          |
| `preview_drag_pan_js`            | `preview_drag_pan.js`                   | Compatibility export; no active registered caller                       |

`resource-ownership-final.json` binds the original names, exact string hashes,
callers and wheel/sdist members. BaseApp loads `safe_dom.js`,
`knowledge_graph_viewer.js`, D1's `file_browser_refresh.js`, then `main.js`.
Existing CSS/head/PDF resources retain their owners and timing. Index-specific
CAPTURE/APPLY strings remain small delegation glue in the Web adapter;
DOM-dependent local drag styles remain in their original callback. No second
runtime implementation is created.

Before migration: two Python string/real-registration tests and seven Node
callback behavior cases passed. Final Node runs pass **42/42**, covering effective
focus/error handling, URL key events, delayed recommended-paper/scroll actions,
storage, PDF/frame and drag/touch contracts, D1 ordering and existing security/
graph/desktop configuration contracts. Python loader coverage is not used as a
substitute for JS behavior. Actual local wheels/sdists and outside-repository
clean-wheel loads pass with **no PYTHONPATH**, real installed ChatPage imports,
resource-prefix checks and network denial (`source-clean-wheel.log`).

### D3: real index, graph and Studio seams

Each product correction has a failing unit/browser expectation before its own
fix commit; no defect fix is hidden in the D2 resource move:

| Reproduced defect and red evidence                                                                                                                                | Minimal corrected boundary                                                                                                                                                 |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Note conversion expected `source_id`, but the real index result contains file metadata (`d3-note-source-red`)                                                     | Reuse authenticated `resolve_file_refs` for the server-materialized note basename when the old result-ID helper yields no IDs                                              |
| Authorized group selection was removed on refresh; Focus showed raw group JSON (`d3-group-refresh-red`, `d3-group-cards-red`)                                     | Keep the same authorized group option and use the existing selection normalizer for displayed member IDs                                                                   |
| A completed old Studio callback overwrote a newer view (`d3-studio-view-red`, `d3-studio-restore-late-red`)                                                       | Compare the existing generation-store ownership token around the real operation; retain its authorized side effect, skip stale component outputs                           |
| Reload did not restore saved artifact cards (`d3-studio-restore-contract-red`)                                                                                    | Extend the existing restoration renderer using authenticated Notebook reads and the existing artifact renderer; retain the old renderer entry and before/after view checks |
| Real mode/files/identity selector triples reached Mind Map as user IDs (`d3-studio-selector-red`, `d3-group-mindmap-red`)                                         | Pass the existing explicit selector mapping in the Web adapter; retain legacy direct-call shapes and reuse group normalization                                             |
| Mind Map inserted an unpersisted synthetic chat turn; subsequent Runtime/Web reference histories diverged (`d3-artifact-history-red`, `d3-graph-send-disconnect`) | Keep artifact/trace/viewer outputs and Notebook persistence; return no-update for actual chat, retrieval and plot histories                                                |

The complete App runs on Windows in Microsoft Edge with Gradio 4.39.0. It uses
actual browser upload inputs, index services, request
identity, SQL persistence and natural event tails. Only deterministic model/
network boundaries are substituted. The final four fresh-runtime/browser batches
pass **32 scenarios**, including all **13 retained R3-C scenarios** and the
separate public fixture (`browser-verified.json`):

| Verified browser scope                   | Actual exercised behavior                                                                                                                                                                                                                                                                                                                     |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Retained chat/conversation/preview flows | Two-turn stream, citations/cache, auto/manual naming, Runtime/Web write pairs, refresh, empty/same-file conversations, delete cancel/confirm/last item, late request/delete, URL/file upload with two users, error/disconnect, slow view/source switches, filter/cards/pages/PDF search/special characters and public read/write restrictions |
| D1 races                                 | All 11 barrier-controlled intent/catalog/browser interleavings described above                                                                                                                                                                                                                                                                |
| Real index manager                       | Browser upload, select/Close, force reindex with a new source ID, Go to Chat, single deletion, bulk confirmation cancel/confirm, notification refresh and other files retained                                                                                                                                                                |
| Groups                                   | Create/select/update/Close/delete, Go to Chat with both members, grounded multi-document Mind Map and other-user invisibility; deleting a group retains its files                                                                                                                                                                             |
| Revoked preview                          | Hold a real preview timer, delete its owned source through the manager, release it: exact `PreviewAccessError/source_unavailable`, cleared selector/card, no other file touched                                                                                                                                                               |
| Studio notes/artifact/graph              | Manual/answer note save, citations, empty-save behavior, refresh/restore, note→indexed source, Mind Map picker Close, generate/save-as-note, actual Markdown export bytes/hash, graph-node question draft→send and aligned real conversation/reference history                                                                                |
| Studio failure/lifecycle                 | Visible no-source failure with empty source IDs, held generation→new conversation, disconnect after real artifact save→fresh-browser restoration of exactly one artifact                                                                                                                                                                      |
| Separate public fixture                  | Owner uploads and generates an actual artifact; non-owner can read saved notes/cards but save/convert/export/delete/generate attempts are rejected with no persisted mutation or export                                                                                                                                                       |

The product's single-file delete acts immediately; its Close button cancels
selection, while bulk delete has a real confirmation/cancel pair. Studio's
available cancel path is closing the generation picker; no in-progress artifact
cancel button is invented. The actual artifact path accepted here is Mind Map,
including export; other artifact types and router behavior are not certified by
this fixture. Existing chat stream/disconnect cancellation protection is retained.

Observer failures are kept distinct from product defects. A monolithic expanded
run exceeded the original 600-second harness budget; it is retained as failed,
then the entire matrix was run in bounded fresh batches. Hidden Dataframe
measurement rows, queue timing and duplicate generated conversation names were
corrected in the observer. In the first final batch at `04a5f179`, reindex left
the same filename in Upload result before its refresh tail completed, so the
observer selected an already replaced ID; the service correctly rejected it.
`1275486e` waits for the new ID in the naturally rendered file table before a
single click. This changes no product logic, permissions or retry behavior.
The next run at `1275486e` also exposed a click on the old row index before a
filter transition finished; Gradio rejected that mismatched index. Cleanup then
masked the original error by releasing an uncreated barrier. `b5534440` asserts
the single filtered row has rendered before the sequential click, and only
releases an armed barrier. Those failed logs remain; this is not a claim to
have redesigned Gradio's concurrent table-selection protocol.

Preview errors are not globally ignored: the committed observer requires the
exact deleted file/browser, timer callback, captured exception type and
`source_unavailable` code. The controlled deletion case must produce that refusal;
all other unexpected JS/preview failures fail the harness. An isolated database
test also verifies rejection before payload reads while the physical file still
exists (`test_preview_owner_scope.py`). Group Go-to-Chat can emit the existing
Gradio vocabulary warning while its choices notification is pending; the final
group token, member cards, exact artifact source IDs and private-user isolation
are separately asserted. The warning is recorded independently of NLTK.
The diagnostic audit also records queued index-selection reads refused after
the same browser deletes that exact source; the real deletion/clear tail still
completes. Their source IDs and completion order are checked separately from
the controlled preview refusal. Existing non-admin `list_users` refusals and
the six deliberately forbidden public-Studio writes are individually classified
in `browser-diagnostics-verification.json`, not silently counted as successful
callbacks or grouped under NLTK.

### Preserved boundaries and verification

All **65 old ChatPage signatures/decorators** remain. The renderer, runtime,
session reads/mutations, Notebook/artifact service, source/group permissions,
graph builder, preview runtime/service, generation store and message event
module remain byte-identical to the round base. Selector identity/SQL call ASTs
are unchanged (`retained-scope-verification.json`). No schema, transaction,
deletion policy, streaming protocol, route/validation algorithm or production
default was changed. Existing R1/R2 cold imports and R3-A/B/C compatibility
contracts remain in the full suites.

Real registration has **367 functions** versus 361. Six JS application nodes
are added by D1; callback-name counts otherwise match. Sending still returns
12 items and retains all nine submission/runtime/completion role names and
arities. Conversation restoration's trace renderer adds only conversation/user
inputs; its existing event edges/order remain. This is an explicit event change,
not an unchanged-whole-graph claim (`event-registration-comparison.json`).
PreviewAccess, actual request injection, view revision/generation ownership,
full/page-history separation and restoration/completion guards remain in use.

Local full affected suites (`libs/ktem/ktem_tests`, `libs/slide_cli/tests` and
the related benchmark/bootstrap/isolation/desktop sidecar consumers):
**3442 passed, 99 failed, 7 skipped, 43 warnings**.
All 99 failure nodes and failing-test bytes match the accepted R3-C evidence;
no new local failure or new skip is introduced. The nine distinct warning
bodies also match; the two extra warning emissions arise from the new real
Gradio Blocks contract using the existing FastAPI `on_event` path. This full
local run remains FAILURE, not a claimed pass (`local-failure-verification-final.json`,
`local-warning-comparison.json`).

Full ruff/hygiene, explicit-file pre-commit, fixed-Dev/round-base hygiene,
constraint/container parity and supply-chain policy checks pass. Four actual
wheels and four sdists build and pass Twine; clean-wheel installations and
public CLI/bootstrap/resource checks pass. Local archive inspection verifies
47 retained/touched members. CI independently verifies all eight distribution
hashes, provenance/SBOMs and 50 ktem source/resource members against the final
source. Local builds include the preserved user assets; CI uses the committed
tree. Final Linux suite and coverage figures are below.

[Stable quality run 34824848584](https://github.com/262412/MARA/actions/runs/34824848584) uses final source
`b553444086b0d4c060a36a9cf07d3bbde94d2904` and the unchanged fixed-Dev comparison input.
It completes with **8 FAILURE, 12 SUCCESS**;
overall **FAILURE**. These counts are this run's actual results,
not assumed future outcomes. All functional/static/collection/build/clean-wheel,
frontend and coverage jobs pass. The three Python audits, three container
baseline checks, repository Gitleaks and required summary fail. The built-image
secret check passes. `quality-final.json` retains each job and step conclusion.

| Final Linux regression job   | Actual result                                                                    |
| ---------------------------- | -------------------------------------------------------------------------------- |
| ktem isolated runtime        | 3372 passed, 47 warnings in 694.50s (0:11:34)                                    |
| kotaemon Python 3.10         | =========== 381 passed, 10 skipped, 93 warnings in 179.59s (0:02:59) =========== |
| kotaemon Python 3.11         | =========== 381 passed, 10 skipped, 93 warnings in 180.26s (0:03:00) =========== |
| Benchmark and root contracts | 1622 passed, 8 warnings in 747.90s (0:12:27)                                     |
| slide_cli                    | PASS (existing quiet pytest invocation; no numeric summary emitted)              |
| Unified pytest collection    | Unified pytest collection passed: 5678 tests (minimum 1260).                     |

The earlier run [34822233006](https://github.com/262412/MARA/actions/runs/34822233006)
at `04a5f179` ended **CANCELLED** with 11 successful, 7 failed and 2 cancelled
jobs when the unchanged workflow concurrency policy superseded this task
with the final source. Its partial coverage is not final acceptance evidence.

A local Actions status GET returned SSL EOF (`ci-phase12-run.json`); the
subsequent bounded read succeeded for the same run/source. That transport
record is retained separately and is not counted as a CI job failure.

The fresh warning-body comparison differs only in the existing
`word,language` / `language,word` PromptTemplate set order; unchanged
template/test bytes and the retained fresh-process hash-seed proof are
checked in `warning-final-verification.json`. No unexplained warning body or image-warning line remains. The new real
Gradio Blocks test reaches two existing FastAPI `on_event` deprecation
paths. The normal ktem count changes 45→47. Its coverage execution changes
46→47: those two additions accompany one fewer existing Gradio analytics
version notice in the unchanged SSO test (five→four). The complete warning
sections, SSO/auth test bytes and lock are compared in
`warning-emission-inspection.json` and `warning-count-comparison.json`;
the initial analysis helper assumption of +2 for both runs was corrected
to the observed counts. All other suite warning counts match R3-C.
`warnings-final.json`, `warning-count-comparison.json` and
`image-warnings-final.json` retain the separate comparisons.

| Coverage scope             | Covered statements / total | Actual / unchanged floor |
| -------------------------- | -------------------------- | ------------------------ |
| benchmark                  | 17146/19005                | 90.218% / 90%            |
| slide_cli                  | 2144/2837                  | 75.573% / 70%            |
| kotaemon                   | 7521/10727                 | 70.113% / 60%            |
| ktem                       | 42941/51341                | 83.639% / 50%            |
| fixed_dev (`adab3f4d`)     | 910/935                    | 97.326% / 90%            |
| r3d_increment (`29e489bf`) | 159/160                    | 99.375% / 90%            |

The directly added/changed Web boundaries are present in the existing collector:

| Module under `libs/ktem/ktem/`                | Covered / statements |
| --------------------------------------------- | -------------------- |
| `app.py`                                      | 208/231              |
| `index/file/_chat_upload_events.py`           | 134/137              |
| `index/file/_selector_ui.py`                  | 91/107               |
| `index/file/ui.py`                            | 190/270              |
| `pages/chat/__init__.py`                      | 427/640              |
| `pages/chat/chat_conversation_events.py`      | 32/32                |
| `pages/chat/chat_gradio_adapters.py`          | 95/95                |
| `pages/chat/chat_knowledge_graph_bindings.py` | 30/32                |
| `pages/chat/chat_layout.py`                   | 138/148              |
| `pages/chat/conversation_restore.py`          | 49/49                |
| `pages/chat/file_browser_updates.py`          | 41/41                |
| `pages/chat/studio_artifact_controls.py`      | 82/100               |
| `pages/chat/studio_artifact_generation.py`    | 81/99                |
| `pages/chat/studio_artifact_mindmap.py`       | 64/71                |
| `pages/chat/studio_callback_identity.py`      | 36/36                |
| `pages/chat/studio_note_actions.py`           | 77/92                |

Coverage artifact `10341686419` has SHA-256
`dd77c1b5fbaacfafb125e4ea0a971e32ccab107c8692a0729f4f553027d28b10`. `coverage-verified.json` also checks
the retained R1/R2/R3 modules, package floors and both production diffs using
the unchanged gate functions. This does not claim 100% coverage for every
touched legacy module or use delegated lines alone as acceptance.

No collector scope, omit/skip list, threshold, debt baseline, lock or required
job was weakened. Subprocess coverage, canonical source paths and absence of
temporary-runtime aliases are checked in the downloaded evidence. JS behavior
has its own Node/browser evidence.

### Security and R3 closeout matrix

Fresh dependency scans report the same keys in all three actual profiles:

| Profile           | Actual job / result      |
| ----------------- | ------------------------ |
| `root-py310`      | `103914616162` / FAILURE |
| `root-py311`      | `103914616112` / FAILURE |
| `container-py310` | `103914616212` / FAILURE |

| Package / version       | Blocking ID(s) in each profile                                             |
| ----------------------- | -------------------------------------------------------------------------- |
| `chromadb==0.5.16`      | `PYSEC-2026-3813`, `PYSEC-2026-3814`, `PYSEC-2026-3815`                    |
| `nltk==3.10.3`          | `GHSA-8mgp-746c-j5xp`                                                      |
| `pypdf==4.2.0`          | `PYSEC-2026-3910`, `PYSEC-2026-3911`, `PYSEC-2026-3912`, `PYSEC-2026-3913` |
| `transformers==4.56.2`  | `PYSEC-2026-3929`                                                          |
| `unstructured==0.15.14` | `PYSEC-2026-3930`                                                          |

The NLTK record is `GHSA-8mgp-746c-j5xp` / `CVE-2026-81726`; the nine
PYSEC records and their prior alias evidence remain explicitly retained in
`security-key-reconciliation-final.json`. No new or resolved profile key
appears relative to accepted R3-C. Alias logic, baselines and scan scope
remain unchanged; this comparison does not close S1.

The new **Trivy 0.70.0** full/lite/ollama scans retain the two HIGH PCRE2
blocking keys `libpcre2-8-0==10.42-1|CVE-2026-86145` and
`libpcre2-8-0==10.42-1|CVE-2026-89161`, with reported fix
`10.42-1+deb12u1`. The package and layer match R3-C; no new raw/blocking
keys, secrets or misconfigurations appear. These remain new relative to
the frozen security baseline, not newly introduced in R3-D. Actual
image builds, retained provenance and runtime smoke pass for Linux/amd64
full/lite/ollama. Docker still collects `libs` into non-editable wheels and
copies the installed environment. The separate post-scan SPDX image SBOM
step is **SKIPPED** after each baseline failure; it is not claimed as
generated. BuildKit attestation and Trivy evidence remain available.

| Image  | Artifact ID   | Artifact SHA-256                                                   |
| ------ | ------------- | ------------------------------------------------------------------ |
| full   | `10340710947` | `fd8a7528163cde3475c8442ffed0630c0b3e81cf234f8f806b871004c7f4c7a9` |
| lite   | `10340082952` | `6e8c7f5826910bf587fe52ff6dc9f2f6d30dd3d37044c9fb4dd3764a2efae775` |
| ollama | `10340038226` | `db09b8aa53f84692413c82f3b85190d7fe55de2b842dc5a8c4866ce0fae40c7c` |

Gitleaks additionally reports `generic-api-key` at
`libs/ktem/ktem_tests/test_chat_javascript_resources.py:12`, introduced in
`b0491128`. This value is exactly SHA-256 of the public baseline
`fetch_api_key_js` string, not an authentication credential. The baseline
string and packaged resource compare byte for byte; recomputing their digest
equals the fixed test expectation (`gitleaks-checksum-finding.json`, final CI
log). Both history and current-worktree scans remain failed. No inline ignore,
allowlist, scan-scope change or history rewrite was used. This new required-check
failure is separately classified; it is not part of the old 99/NLTK blockers.

The former R3 remaining table is now the following evidence/status matrix:

| R3 item                                                             | Evidence/status at this round                                                                                                                                                                                                   |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Startup/filter/index-refresh concurrency                            | **Verified, awaiting review**: D1 red proofs, 11 complete barrier/browser cases, real request and per-browser vocabulary/intent protection                                                                                      |
| Frontend callback/resource ownership                                | **Verified, awaiting review**: eight unique resources, unchanged effective strings and callbacks, explicit load/caller/archive mapping, 42 Node contracts                                                                       |
| Web wheel/sdist and repository-external loading                     | **Verified**: actual local and final CI builds/clean wheels, installed ChatPage resources without PYTHONPATH                                                                                                                    |
| Container resource collection/runtime                               | **Build/provenance/runtime verified for Linux/amd64 full/lite/ollama**; source-bound image build/provenance/runtime evidence retained; vulnerability gates remain separate failures                                             |
| Desktop resource collection                                         | **Static/config contract verified only**: native React/PyInstaller sidecar explicitly excludes Gradio; collection config/Node tests checked. No desktop binary build/install executed or claimed                                |
| Index management and notifications                                  | **Verified, awaiting review**: actual upload/reindex/select/Close/single+bulk delete/group flows and notification/catalog races; no broader deletion semantics                                                                  |
| Authorized preview/navigation and graph/source/citation interaction | **Verified, awaiting review**: retained preview/PDF/source-switch tests, exact revocation refusal and real graph-node→question→stream/citation persistence                                                                      |
| Studio notes and one actual artifact path                           | **Verified, awaiting review**: save/restore/convert, Mind Map/export, picker cancel, failure/disconnect/view ownership and public non-owner refusal. Other artifact types and nonexistent cancellation controls are not claimed |
| S1/PCRE2 and new Gitleaks checksum finding                          | **BLOCKED**: unchanged scans/gates and actual failing CI evidence; no dependency/security upgrade in R3-D                                                                                                                       |

### Protection and stop point

All **133 pre-existing asset/instruction changes** remain byte-identical; the
untracked `NUL` entry is preserved. Only explicit round paths were staged.
Canonical environment/real configuration/database/cache metadata, worktree
inventory and historical cleanup-refused directories are compared before/after
in `r3d-final-state.json`. All final browser runtimes are owned and removed.
No canonical sync, branch/worktree creation, force push, merge, deployment or
release occurred. The retained R0/R1 history below remains byte-identical.

Evidence root:
`D:/PythonProject/MARA-refactor-review-20260910-01a086ff/r3d-web-closeout`.
Stable CI evidence:
`D:/PythonProject/MARA-refactor-review-20260910-01a086ff/r3d-stable-ci`.
`execution.jsonl` records commands, source SHA, dirty-file hashes, environment,
exit codes and logs. Report/source push receipts and final-state receipt bind
the actual local/remote commits; the report-only tree reuses source evidence
only after byte-equivalence checks.

**Stop at R3-D. Await independent closeout review before R4.
S1/PCRE2 remain open; merge/release remains NO-GO.**

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
