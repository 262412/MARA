# Task 13 Final Verification and Risk Rescan Report

Date: 2026-07-12

Status: **BLOCKED — release remains frozen**

Comparison base: `f72a9a3f609186eba6ff2f9153f0ae7cc43d1a24`

Verified local HEAD: `1edc0bc48875996a4cadd596ab182fba4965c81c`

## Executive result

The locally executable functional, browser, static, packaging, lock, hygiene,
coverage-floor, npm, and Python distribution gates are green. The original
high-risk authentication, DOM-XSS, deletion consistency, artifact isolation,
owner authorization, callback identity, packaging, and release-containment
findings now have regression coverage and fail-closed implementations.

Task 13 cannot be marked complete because three required release gates are not
green:

1. Production diff coverage against the full hardening base is **86.76%**
   (`5838/6729` statements), below the required 90%.
2. Current `uv audit` reports 319 root findings (292 with fix versions) and 321
   container-resolution findings (292 with fix versions). The audit schema has
   no severity field, but the repository's current raw audit job fails on these
   findings. Resolving them requires a separately reviewed dependency-upgrade
   wave; the hardening plan explicitly prohibited silently changing the locked
   baseline inside unrelated security/refactor changes.
3. Docker, Trivy, Gitleaks, Syft/Cosign, and local Python 3.11 are unavailable.
   Consequently real three-target image build/runtime/secret/CVE evidence,
   full-history secret scanning, and the kotaemon 3.11 suite require hosted CI.

Credential rotation/invalidations, required-check configuration, and approval
of release unfreezing are also external operator actions and were not asserted.

## Risk rescan

Using the repository's same AST hygiene collector:

| Metric                          | base allowance | current actual | change |
| ------------------------------- | -------------: | -------------: | -----: |
| debt files                      |             88 |             73 |    -15 |
| modules over 600                |             20 |             19 |     -1 |
| functions over 80               |             93 |             72 |    -21 |
| classes over 300                |             29 |             29 |      0 |
| non-actionable broad exceptions |            140 |             85 |    -55 |

The committed ratchet is intentionally slightly above current actual where
untouched compatibility debt remains: 79 files, 20 module allowances, 82
function allowances, 29 class allowances, and 89 broad-exception allowances.
It never widened relative to the base. Task 12D removed six stale preview
entries and lowered both remaining preview hotspots.

The repository still has no pinned cyclomatic-complexity collector or original
same-method complexity snapshot. This report therefore makes no unsupported
claim that the historic “69 high-complexity functions” figure was reproduced;
length and broad-exception counts are the reproducible current metrics.

### Revised risk rating

- Active authentication/data-consistency/DOM-XSS risk: **2.5/10** based on the
  implemented boundaries and fault/browser regressions.
- Release and supply-chain risk: **7/10** until dependency and hosted scanner
  gates pass.
- Maintainability risk: **5/10**; debt fell materially, but 19 oversized
  modules, 72 oversized functions, 29 oversized classes, 85 non-actionable
  broad catches, and the two preview classes recorded in Task 12D remain.
- Overall current “屎山风险”: **about 5/10 (medium)**, improved from 8/10 but
  not yet at the ≤4/10 acceptance target.

## Functional and test evidence

| Gate                                    | Result                                                           |
| --------------------------------------- | ---------------------------------------------------------------- |
| unified collection                      | 2094 collected; minimum 1260                                     |
| benchmark/root suite under coverage     | 418 passed                                                       |
| kotaemon under coverage                 | 346 passed, 8 skipped                                            |
| ktem under coverage                     | 1200 passed                                                      |
| slide_cli final package suite           | passed                                                           |
| focused auth + deletion fault injection | 241 passed                                                       |
| Node DOM/source tests                   | 18 passed                                                        |
| real Chromium security/preview flows    | 8 passed                                                         |
| package line floors                     | benchmark 90.14%, slide_cli 74.29%, kotaemon 68.95%, ktem 68.07% |
| aggregate production coverage           | 72.14% (`32287/44753`)                                           |
| production diff coverage                | **86.76% — FAIL, required 90%**                                  |

The coverage driver initially found a stale slide_cli runtime probe after the
Task 12F `user_id` contract. The test double was fixed, slide_cli was rerun, and
the complete four-package coverage driver then exited 0 for package floors.

## Static and hygiene evidence

- Black all-files: green; two remaining Markdown-only changes were committed
  separately as `4e90ac0`.
- Stable full pre-commit: green, including hygiene, YAML/TOML, whitespace,
  credential/private-key checks, Black, isort, flake8, autoflake, Prettier,
  mypy (including kotaemon and slide_cli conftests), and codespell.
- Ruff full repository: green.
- Full hygiene ratchet and base-vs-branch widening guard: green.
- `git diff --check`: green; worktree clean.
- Root `uv lock --check --offline`: green.
- Docker lock initially failed because Task 12E2's direct `filelock` dependency
  was absent. `docker/uv.lock` was corrected in `8a0f4a9`; root/docker lock,
  constraints sync, and container lock parity are now green.
- `uv pip check --python .venv/bin/python`: 390 packages compatible.

## Frontend/browser security evidence

- The cached, locked Playwright Chromium was reused; no browser was downloaded.
- Generated (not committed) PDF/DOCX/PPTX binaries exercised the exact
  malicious payload contracts through a focused real Gradio Blocks harness.
- PDF.js rendered the hostile PDF and navigated page 1→2→3 in the same iframe.
- DOCX/PPTX unsafe links and SVG image packages remained inert; document
  iframes had no script capability.
- Corrupt Office diagnostics remained escaped; answer rendering stripped
  script, event, form, JavaScript/data-HTML and active SVG content.
- All marker, popup, dialog, navigation, and attacker-host request counters
  stayed zero.
- Real HTTP requests proved app-data siblings, other PDF.js versions, and file
  storage are denied. Gradio's framework upload directory remains inherently
  route-visible and must contain no secrets.

## Packaging and distribution evidence

- Built and `twine check`-validated four wheels and four sdists for `ktem`,
  `kotaemon`, `mara-research-cli`, and `mara-app` under node-local `/tmp`.
- Clean layered installation smoke passed for both `MARA` and `MARA-cli`,
  DocQA/App commands, representative imports, icons, Help/legal content, and
  offline `MARA app init` PDF.js materialization.
- Generated and verified SPDX, CycloneDX, and local SLSA-style provenance for
  all eight artifacts (25 evidence files including the index).
- No package or image was uploaded or published.

## Dependency and scanner evidence

- `npm audit --audit-level=high --json`: 0 info/low/moderate/high/critical
  findings across the locked Node tree.
- `uv audit` current results:
  - root Python 3.10: 399 packages, 319 findings, 292 fixable;
  - root Python 3.11 resolution: 399 packages, 319 findings, 292 fixable;
  - docker Python 3.10: 310 packages, 321 findings, 292 fixable.
- The JSON does not expose severity, so this report does not invent a
  HIGH/CRITICAL count. The current workflow's raw audit semantics fail.
- Supply-chain policy and 51 workflow/container/release contract tests pass,
  but these are not substitutes for Gitleaks/Trivy/Docker evidence.

## Storage and quota

- Repository source remained under scratch; `.venv` remained a symlink to
  `/mnt/fastscratch/users/tbczhang/envs/mara`.
- No repository-root `data/`, `datasets/`, `outputs/`, or `ktem_app_data`
  directory was introduced.
- High-inode runtimes, coverage, distribution builds, clean-wheel environments,
  and evidence were placed under `/tmp`.
- Clean installation/audit activity expanded the reusable uv cache and pushed
  fastscratch over its soft file quota. The disposable uv cache was cleaned
  after evidence capture (101,409 files / 9.0 GiB removed).
- Final fastscratch: 309,247,100 KiB and 448,048 files, below the 500,000 soft
  file limit.
- Final scratch: 75,417,864 KiB and 474,969 files; still above its 300,000 soft
  file quota but below the 500,000 hard limit, with grace active. No new
  repository test environment was created there.

## Change scope and public surface

From base to verified local HEAD: 243 commits, 374 changed files, 50,177
insertions and 8,511 deletions. The exact file list is reproducible with:

```bash
git diff --name-status f72a9a3f609186eba6ff2f9153f0ae7cc43d1a24..HEAD
```

Major changed groups are release/Docker/CI policy; authentication and runtime
bootstrap; deletion/storage lifetime; Web callback and Notebook authorization;
preview/PDF.js/Office security; DocQA request/session/runtime services; Gradio
adapters; packaging metadata/assets/legal files; benchmark/CLI parity; and the
associated regression/browser/quality tooling.

`MARA` and `MARA-cli` command names, existing options, success JSON keys,
DB/session shapes, Gradio component ports/event order, and authorized callback
return shapes are preserved. Intentional compatibility changes are managed-mode
server identity, fail-closed network authentication, bcrypt migration, safer
preview URLs/cache names, active existing Office timer polling, and one-release
deprecated environment/extra mappings.

## Required next actions

1. Keep PyPI and Docker publishing frozen.
2. Open a dedicated dependency-upgrade wave, prioritize directly reachable
   runtime packages, enrich audit findings with severity, update locks and
   constraints together, and rerun all package/browser/container gates until
   fixable HIGH/CRITICAL findings are zero.
3. Add tests for at least 218 currently uncovered changed production
   statements (or otherwise legitimately improve coverage) to raise diff
   coverage from 86.76% to ≥90%; do not weaken the threshold.
4. Run hosted Python 3.11, full-history Gitleaks, and Docker lite/full/ollama
   build, runtime smoke, Trivy secret/vuln/misconfig, SBOM and provenance jobs.
5. Confirm all exposed credentials were rotated/revoked, configure required
   checks/branch protection, and only then approve release unfreezing.
6. Continue architectural slices for the remaining oversized preview classes
   and other actual hygiene debt; lower the baseline after each real split.

Task 13 verdict: **BLOCKED, NOT COMPLETE**. Local functional hardening is
substantially complete, but the release and ≤4/10 final acceptance conditions
are not yet satisfied.
