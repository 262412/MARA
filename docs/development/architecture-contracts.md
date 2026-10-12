# Architecture contracts

This guide records responsibility boundaries implemented during R1–R6. It is
not a claim that every feature, provider or platform has been accepted. Current
compatibility constraints and remaining acceptance limits are summarized in
[refactor boundaries](refactor-status.md). Actual executions belong in their
CI runs or review artifacts.

## Executable boundaries

| Owner                                    | Responsibility and allowed dependency                                                             | Compatibility retained                                                                                     | Existing collection / behavior evidence                                               |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `ktem_contracts.file_selection`          | Neutral normalization and merge rules; no runtime/page import                                     | Runtime and ChatPage adapters; normalize/merge intentionally differ                                        | Root `test_file_selection_import_boundary.py`; ktem source-scope/runtime helper tests |
| `ktem.docqa.finance_plan_policy`         | Finance strategies use schema and helper modules, not planning/runtime facade                     | Planner orchestration, callback injection, original plan identity                                          | ktem `test_docqa_finance_plan_policy.py`, plan characterization and seam tests        |
| `ktem.docqa.evidence_binding_policy`     | Candidate/verification rules; no reverse binder/runtime dependency                                | Binder diagnostics and caller-owned collections                                                            | ktem `test_docqa_evidence_binding_policy.py`, binding characterization and seam tests |
| `ktem.pages.chat.file_browser_rendering` | Presentation from supplied records; no authorization, SQL or filesystem reads                     | Existing page callbacks, IDs and component outputs                                                         | ktem file-browser rendering/update tests; Web event acceptance remains separate       |
| `slide_cli.docqa_inspection`             | Read-only queries/diagnostics; inert import; database/bootstrap imports occur on collector calls  | `docqa_runtime` exports and CLI/Sidecar patch consumers; factory/profile/acceptance remain in their owners | slide_cli inspection boundary, identity and record tests                              |
| `electron/sidecar-launch.ts`             | Command/cwd/env construction; reuse `mergeSidecarEnvironment`; no manager/Electron/process import | Manager methods used by existing patch consumers                                                           | Existing Electron launch/lifecycle tests plus `sidecar-launch-boundary.test.ts`       |
| `kotaemon.agents.tools.mcp_operation`    | Complete operation runs on caller or owned Windows Proactor task; no SDK/config/UI dependency     | Sync and native async facade; cancellation waits for producer cleanup                                      | kotaemon worker/operation lifecycle tests, real owned stdio/SSE contracts             |
| `kotaemon.agents.tools.mcp_session`      | Own SDK connect/initialize/context exit on one task; lazy SDK imports                             | Facade `initialized_session` patch and existing tool schema/type paths                                     | kotaemon MCP contracts/live transports; no new pool or transport                      |
| `slide_cli.deck` / `deck_export`         | Deck owns content/types/patches; export owns external conversion and owned publication            | `deck.export_deck_pdf`, stdlib patch objects and `ShapeSnapshot` type owner                                | slide_cli deck/export/stale-output/resource tests                                     |

Root `tests/test_refactor_architecture_contracts.py` adds semantic AST guards
for these Python dependency directions. In-memory negative controls cover
absolute/relative/literal dynamic imports, forbidden lazy reverse imports,
eager loads in defaults/decorators/classes and rendering I/O. Legitimate lazy
SQL/SDK integrations and helpers remain accepted. Existing subprocess cold
imports and behavioral contracts provide runtime evidence that AST checks
cannot supply. Computed dynamic classpaths are not resolved by this static
guard; real public type and patch consumers remain tested separately.

The Desktop guard uses the parser from the already locked Vite/Rolldown
toolchain, including type imports, exports, dynamic imports and require syntax.
It belongs to `npm run test:electron` and `npm run verify`. Python guards belong
to the existing `benchmark-root` Quality job; package tests remain with their
original package jobs. No new workflow, architecture framework or dependency
policy is needed.

## Retained responsibilities and remaining boundaries

| Original plan domain          | Treatment and bounded remaining work                                                                                                                                                                                                          |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Public CLI and distributions  | Keep `MARA`/`MARA-cli` mapped to `slide_cli.cli:main`; internal `slide_cli`, `kotaemon`, `ktem` names and root `mara-app` are compatibility/package boundaries. Verify installed scripts outside the checkout.                                |
| Web/DocQA                     | Keep workflow composition and accepted R1–R5 owners. U1 async browser application remains deferred/BLOCKED in chat event/selector harness scope, not a prerequisite for independent structure tests.                                          |
| Planning/evidence/benchmark   | Retain runner/scoring modules and frozen fixtures. Structure tests do not establish model/dataset performance, scientific claims or paid-provider readiness.                                                                                  |
| Resource lifecycle            | Retain R5 cache, transaction, Source-lock, Notebook, artifact/download owners and supported process scope. No data migration, historical cleanup or cross-store rollback claim.                                                               |
| Desktop/Sidecar               | Keep manager lifecycle, application services, IPC/SSE/task contracts. Native combination packages, installers, clean VMs and unfinished Notes/Studio/Graph/export/preview are separate capabilities.                                          |
| MCP/agents and deck/artifacts | Retain accepted operation/session/export boundaries and registry services. SSE cancellation does not imply remote rollback; media adapters and external office/provider capabilities remain conditional.                                      |
| App/model/platform commands   | Keep lazy public groups and actual aliases. Test read-only entrypaths and installed coding-tool bundles with owned targets/fake configuration; never write real `.codex`/`.claude` directories for verification.                              |
| Containers/build/resources    | Four distributions, legal files, PDF.js/JS/CSS/platform assets, package manifests and native resources remain explicit delivery contracts. Security/PCRE2 failures independently block release.                                               |
| Docs/developer tools          | Current setup uses the storage/hygiene contracts and locked CI. Generated schemas, locks, vendor licenses and fixtures are runtime or verification inputs. Maintain durable guidance in existing docs; remove superseded planning narratives. |

The tracked-tree reconciliation reuses the original R0 classifications and Git
blob identities. Its file denominator covers repository-owned tracked domains;
it does not turn unchanged files into verified features or include protected
working overlays in package inputs. Major unresolved work stays limited to its
actual owner and evidence gap. No blanket package renaming, compatibility-layer
deletion, global DI/repository framework or automatic security upgrade follows.
