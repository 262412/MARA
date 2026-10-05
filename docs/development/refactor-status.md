# Safe refactor status

## Current S1-4B PDF compatibility review (2026-10-05)

**The platform fixes and both original complete tests are committed and pushed.
The revised PDF dependency candidate is BLOCKED by a new Pydantic constraint
and a reproduced Gradio-client schema failure; no complete candidate was
installed.** This round starts at
`6bbd36a94b6c1c05b4e01a1c5735dae0c01b8a33` on `codex/r0-r1-safe-refactor`.
The user explicitly skipped Linux execution during this round. Batch 4 is not
complete; R6-D remains **BLOCKED / not ACCEPTED**, U1 is deferred, the historical
mypy incident is **OPEN**, and merge/release remains **NO-GO**.

### Completed platform and baseline-test delivery

- `bc2b16e7c5b97f3263f80f8cfea44c2e336e0edb` fixes the three first-party
  capability/type seams and adds their adjacent tests. Narrow `Callable`
  bindings resolve native `pread`/`fchmod` after the existing guards. They retain
  positioned reads, file-identity checks, fd permission operations, error order
  and cleanup. No seek/read or path-chmod replacement, ignored type error,
  fabricated stub or weakened checking is introduced.
- `656c3e56a6304e50be4d82f10a4831965e8bec4e` commits both complete original
  PDF/preview tests. Their bytes match the preserved S1-4A hashes; neither test
  was reduced or replaced to pass the hook.

The original hook manifest, including mypy **1.7.1** and hygiene, passes on the
seven affected files. Both commits also automatically run that original manifest
through the reviewed cache/env/cwd boundary. The actual baseline runtime gives
**35 PASS / 6 SKIP**: the original 25 PDF and 3 preview cases plus 7 portable
platform cases pass. The six native POSIX cases are skipped on Windows and
**NOT RUN on Linux**, per the user's instruction. They are not POSIX runtime
proof. The original five-error hook output remains preserved.

### Changed candidate conditions and capability mapping

The candidate uses a full source archive of **656c3e56**, including the tested
platform changes. Its manifest removes the meta-package and the hard identities
of agent-openai, program-openai and question-gen-openai. Its inventory covers all
twelve original supplied capabilities and the nine original dynamic classpaths;
SimpleFile/Chroma/LanceDB/Milvus/Qdrant requirements remain in scope.
The actual first-party ReAct/ReWOO policies and LangChain agent wrapper are
unchanged. Absence of a direct import is not treated as permission to remove a
capability.

The exact official core **0.13.6** wheel provides workflow `FunctionAgent`, not
the old `from_tools`/`chat`/`achat`/stream-chat interface. Core
`FunctionCallingProgram` can be investigated for structured output and
subquestion adapters, but a completion-based question generator is not assumed
equivalent. These are **mapped candidates, not proven replacements**. No alias,
fake third-party namespace, site-packages patch or Agent migration is delivered.
The old raw `llama_index.agent.openai.OpenAIAgent` classpath remains a required
explicit migration decision and compatibility contract.

The selected combination is pypdf **6.19.0**, core **0.13.6**, readers-file
**0.5.2**, chroma integration **0.5.0**, and chromadb **0.5.17**. Exact companion
versions, official metadata hashes, consumers and pending contracts are in
`evidence/candidate-selected-metadata-01.json` and
`evidence/capability-mapping-01.json`. Both root and Docker retain their Python
ranges, marker branches, CPU torch strategy and unrelated pins. The first new
resolver conflict requires managed-cloud's exact `llama-cloud==0.1.35` instead
of frozen 0.1.42; readers-llama-parse also requires `llama-parse>=0.5`. Only those
necessary integration dependencies are unfrozen for the second attempt.
Checking managed-cloud 0.9.4 metadata confirms the same 0.1.35 requirement; no
cloud SDK is installed or changed in the primary environment.

Pinned uv **0.11.19** then reports the following independent conflict in both
the full root universal and Docker resolutions:

```text
llama-index-core==0.13.6
  -> llama-index-workflows>=1.0.1,<2
  -> pydantic>=2.11.5
MARA retains pydantic<=2.10.6 (locked at 2.10.6)
```

All four eligible workflows releases have that Pydantic floor in their official
metadata. Core 0.13.0 already requires the same workflows range, so its metadata
does not offer a lower-floor escape. A separate Windows Python 3.10 two-input
resolution reproduces the conflict; changing only its Pydantic requirement to
2.11.5 resolves. This is a new constraint set, not a rerun of S1-4A's fixed Agent
distribution identities. The positive control is not a complete MARA solution.
No valid candidate lock is produced: the two lock files in the candidate copy
still contain the baseline locks and are explicitly marked unusable for this
candidate.

### Concrete stop boundary and unexecuted contracts

A separate, legally resolved and hash-checked minimal environment passes its
dependency check. It exercises the real Pydantic dictionary schema and the
unchanged **gradio-client 1.1.1** conversion function. With Python **3.10.19** and
identical client source hashes, Pydantic **2.10.6 passes**, while **2.11.5 emits
`additionalProperties: true` and fails with
`TypeError: argument of type 'bool' is not iterable`**. The paired processes have
15-second user CPU, 768 MiB process/job memory and 30-second wall limits. This is
a schema-boundary counterexample, not a complete MARA installation or U1 run.
It agrees with the upstream [Gradio schema issue](https://github.com/gradio-app/gradio/issues/10792).
Continuing this route needs a separately reviewed Gradio/client compatibility
change or maintained backport, beyond this round's authorization.

| S1-4B item                                                                      | Actual result                                               |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Platform fixes, original full tests, automatic commit hooks                     | PASS; two commits pushed                                    |
| Baseline PDF/preview and portable platform contracts                            | 35 PASS; six native POSIX cases skipped                     |
| Twelve-capability and nine-classpath mapping                                    | Static inventory complete; replacement equivalence unproven |
| Revised root and Docker candidate resolutions                                   | FAIL: Pydantic/workflows conflict                           |
| Complete candidate install and module/dependency checks                         | NOT RUN: no legal full candidate                            |
| Actual Agent sync/async/tools/errors/history/stream/cancel/callback equivalence | NOT RUN                                                     |
| Candidate page labels, saved citations and original PDF/preview suite           | NOT RUN                                                     |
| Old Chroma collection opened by 0.5.17, writes and rollback boundary            | NOT RUN                                                     |
| Cross-version parser cache invalidation, recovery and old evidence reads        | NOT RUN                                                     |

The refreshed official pypdf 6.19.0 metadata retains the same wheel hash verified
in S1-4A and currently lists no advisories for that release. The prior 49-group
range verification and bounded parser controls remain historical evidence, not
new candidate execution. The known alphabetic-label difference, bounded large
label fallbacks, nonnumeric thumbnail filtering and versionless parser-cache
stamp still require the full candidate contracts listed above. No golden refresh,
reindex or real cache/database migration is performed. Chroma 0.5.16 and 0.5.17
currently share the same three advisory alias groups; this small version change
is not claimed to fix those advisories.

Candidate manifest patches, failed attempts, exact provenance, minimal replay
inputs and schema results remain under
`D:/MARA-s1-01a086ff/s1-pdf4b-20261005/`. Main runtime manifests, locks, AnyIO
4.14.2, Soup Sieve 2.9, PCRE2 u2, OpenAI SDK, Gradio, model stack and Python
policy are unchanged. The historical 135 paths, both preceding 136-path sets,
the 4A/4B opening sets, original PDF tests, seven tested files, NUL and the two
observed historical mypy hashes/mtimes are checked separately. Historical
preimages remain unknown; there is no aggregate protection PASS. Canonical
environment, real data and the eight historical UV incident directories are
not changed. Preparation and launcher failures retain their own logs.

The existing report is the only final documentation change. No full Native,
three-image, Quality, U1 or dual-37 rerun is initiated, and required checks are
not disabled. Stop at **S1-4B compatibility review** with the new constraint and
schema evidence. Formal dependency migration and the remaining actual
Agent/PDF/Chroma/cache contracts require a new reviewed scope.

## Historical S1-4A PDF compatibility review (2026-10-05)

**The tested PDF candidates retaining the original integration distribution
identities are UNSAT; this does not prove that preserving all MARA capabilities
is impossible.** No complete MARA candidate was installed or accepted in S1-4A.
The test-commit blocker described below was subsequently resolved in S1-4B.
S1-4A starts at
`ff52bda593848cf6471de751033995314533ee10` on `codex/r0-r1-safe-refactor`;
the preceding batch's actual CI source remains
`8d6524cb97f2fcd7d95cc8339482d9077df99290`. This round delivers reproducible
dependency conflicts and baseline contracts for review, not a formal batch-4
security upgrade. R6-D remains **BLOCKED / not ACCEPTED**, the historical mypy
incident stays **OPEN**, U1 is deferred, and merge/release remains **NO-GO**.

### Official candidate and actual resolution

The three original batch-3 Python audits each contain **97 pypdf records,
representing 49 advisory alias groups**; the three image audits each contribute
eight matching pypdf records. All pypdf records, original source paths and hashes
are retained in `evidence/pypdf-targets.json`; other dependencies were not
reinvestigated. The official [pypdf 6.19.0 wheel](https://pypi.org/project/pypdf/6.19.0/)
has SHA-256
`7e5d6e730e7dae87d560a2cee218b852f6498c8be61966f3cd02ead971e48d14`.
Its **60 runtime files** match the sdist and official
[release](https://github.com/py-pdf/pypdf/releases/tag/6.19.0) commit
`d62cb58d3988b291b0435eddfd118c4f8f6b6a46`. All 49 upstream advisory ranges place
6.19.0 outside the affected range and at or above the patched version; 48 have
fix references in the changelog, and the remaining LZW follow-up references
release 6.4.0. This verifies provenance and published fix coverage, not 49
independent exploit reproductions. The older 6.16.1 candidate is insufficient.

Two complete task-owned source copies were actually resolved with pinned uv
**0.11.19**: retaining the meta-package, and replacing it with explicit
core/integrations. Both retain all twelve original meta-package dependencies,
the existing vector stores and optional integrations. Both root and Docker
resolutions fail. The root universal solver first reports a Python >=3.13 split;
the Docker Python 3.10 resolution and separate Windows 3.10/3.11 and Linux 3.10
minimal resolutions independently reproduce the conflict. The Python support
ranges and platform markers were preserved, including Windows' milvus-lite
exclusion. The seven packages with multiple marker-selected versions were not
incorrectly flattened into single-version constraints.

The inclusion-minimal retained-integration constraint set is:

```text
pypdf==6.19.0
llama-index-readers-file>=0.1.33
llama-index-agent-openai>=0.2.9
```

Deleting each requirement separately resolves successfully. A fixed-version
two-package reproduction is `llama-index-readers-file==0.5.2` (core
`>=0.13,<0.14`) plus `llama-index-agent-openai==0.4.12` (core
`>=0.12.41,<0.13`); each package alone resolves. Reader 0.5.2 is the first
available version found to allow pypdf 6.x. Keeping the existing OpenAI agent
integration blocks both routes; substituting readers-file 0.7.0 does not remove
that conflict. The input files, complete resolver errors, positive controls and
exact argv/env/cwd are retained under the task's `evidence/` directory.

An independent conflict remains when retaining `chromadb<=0.5.16`: the compatible
reader/core closure requires a newer Chroma integration, whose dependency floor
is `chromadb>=0.5.17`. This proves a package constraint conflict; it does not
prove that a database format migration is required. Agent/classpath continuity
and Chroma compatibility need a separately reviewed migration scope. No
capability was dropped on the basis of grep results. No forced installation,
`--no-deps`, dependency override or METADATA patch was used. Candidate TOML
patches stay in task evidence; no candidate lock was produced. Main dependency
declarations, locks, AnyIO 4.14.2, Soup Sieve 2.9 and the PCRE2 u2 pin are unchanged.

### Executed contracts and bounded parser controls

Against a complete **ff52bda5 source copy plus the two contract-test changes**,
the existing prepared Python 3.10.19 environment gives **25 PDF contract tests
and 3 preview tests PASS**. These use real PDF/PyMuPDF parsing, colored page
thumbnails, page order/text/metadata, decimal/Roman/alphabetical labels,
encrypted and malformed files, document/evidence IDs, task-owned parse caches,
index reloads, and real SimpleFile, Chroma and LanceDB persistence. Nine dynamic
class paths remain importable. Only the external embedding API uses a controlled
substitute. The original runtime plugin isolates all test outputs; no real data
was reindexed and no golden baseline was refreshed.

These are baseline results, not candidate integration results. The existing
thumbnail reader omits nonnumeric page labels. Baseline parser-cache defaults
identify the loader class without dependency versions; passing same-version
reloads does not establish cross-version cache validity. Separate fully legal
parser-only installations of 4.2.0, 6.18.1 and 6.19.0 pass dependency checks and
official runtime-file comparisons. They are not complete MARA installations.
The same four PDF byte streams were read in twelve fresh processes, each with
8 seconds user CPU, 256 MiB process/job memory and a 12-second wall limit.
Oversized Roman labels exhaust the old 4.2.0 memory budget; oversized alphabetical
labels exhaust 6.18.1's budget. Both return bounded physical-page fallbacks in
6.19.0. Ordinary Roman labels agree, while labels beyond Z change from baseline
`AA, AB, AC` to `AA, BB, CC`. These two security cases and the label difference
are retained explicitly; full candidate first-party, persistence and migration
contracts remain **NOT RUN** because the complete dependency set is unsatisfiable.

### Historical delivery blocker and protection

The complete original hook manifest passes all applicable checks except mypy.
It reports five existing Windows attribute errors: `os.pread` in
`artifact_types.py:133,138` and `artifact_manifest.py:203`, and `os.fchmod` in
`preview/cache_attestation.py:94,176`. These production files were not modified.
At the S1-4A stop point, both complete test changes were **uncommitted**:
`libs/kotaemon/tests/test_pdf_reading_contracts.py` and
`libs/ktem/ktem_tests/test_preview_pdf_compatibility.py`. Their final tested
hashes and original failed hook logs are preserved. No hook bypass, weakened
type/import checking, hidden imports or deletion of failing-scope tests is used.
The S1-4A report-only commit therefore did not complete the requested test
commit; that part was **BLOCKED** until the separately authorized S1-4B fixes.

The historical 135 paths, the two preceding 136-path user sets, this round's
136-path opening set, NUL and the two new test-file contents are checked
separately. The two observed historical mypy files retain their post-incident
hash and mtime; their missing preimages remain unknown. There is no aggregate
protection PASS. Controlled subprocess and hook entries isolate actual caches
and temporary paths; canonical installation, real databases/caches and historical
incident directories are untouched. Initial preparation/launcher/test failures
and later corrected attempts have separate logs. Complete Native, three-image,
Quality and U1/dual-37 reruns were not started.

Evidence is under `D:/MARA-s1-01a086ff/s1-pdf4a-20261005/`.
`evidence/delivery-evidence.json` binds the source, candidate patches, replay
inputs, attempts and pending test hashes. Stop at **S1-4A compatibility review**;
neither a security-upgrade completion nor permission for broader migration is
inferred from these experiments.

## Accepted S1 Soup Sieve batch 3 measured scope (2026-10-05)

**The user's October 5 review separately ACCEPTS batch 3's agreed Soup Sieve
scope and the tested hook forward invocation boundary.** It does not close the
historical mypy incident or establish aggregate protection. The user's October 4
review separately accepts batch 2's measured PCRE2 scope and exact Gitleaks
exception. Accepted AnyIO and earlier structure work remain unchanged. R6-D
remains **BLOCKED / not ACCEPTED**, U1 is deferred, the historical mypy incident
is **OPEN**, and merge/release remains **NO-GO**. There is no total protection PASS
and no automatic next dependency migration.

Work starts at `9fea61acdfebf9367971f1b6e0829f5e95b70775` on
`codex/r0-r1-safe-refactor`. The bounded security/semantic tests are commit
`5cb46dd21b399583ea988f39f047137ca692cc5c`; the five dependency files and exact
constraint expectation are commit `8d6524cb97f2fcd7d95cc8339482d9077df99290`.
All new CI and production artifacts below use **8d6524cb, attempt 1**. A final
documentation-only commit follows that execution source.

### Hook forward boundary and historical incident

The original `gitleaks-hooks-02` invocation ran pre-commit from the primary
checkout without `MYPY_CACHE_DIR`. The observed writes are its two primary
`.mypy_cache/3.10/scripts/supply_chain_contracts` files; this is not evidence of
HOME writes. Their initial preimage remains unavailable and historical cache
integrity remains unknown. Neither file was restored, removed or given a new
mtime.

The task-owned launcher now validates the actual argv, executable, cwd and env
snapshot immediately before spawn, including pre-commit's child hooks. Missing,
empty, relative, conflicting, inherited and redirected paths are rejected;
explicit mypy CLI/config cache destinations are checked as well. Tests include
a real junction escaping to the primary checkout. Pinned mypy **1.7.1** was
actually run with `--no-incremental`: its cache files appeared in the owned
cache, and a real invalid-type fixture still failed with the expected diagnostic.
The original complete hook manifest passes on the primary source. Both actual
candidate commits automatically ran that manifest through the task-scoped Git
hook, with explicit files and validated child environments. No hook skip,
type/import-scope change or persistent primary Git/pre-commit configuration
change was made. This demonstrates the tested forward invocation boundary;
it does not establish universal filesystem containment or close the old incident.

### Official candidate, bounded comparison and installation

The official [PyPI 2.9 wheel](https://pypi.org/project/soupsieve/2.9/) has SHA-256
`a2b2c76d67df2382d245409fd71e321a571717e58463efa32ace87dcadac2c12`.
Its seven runtime Python files equal both the sdist and release tag
`8763f914472fc83652babda708bed5c8ef287004`. The failing development HEAD
`751c57b2c7e978e206b94b7dba17f8e2af392e19` in the
[IDENTIFIER/VALUE advisory](https://github.com/facelessuser/soupsieve/security/advisories/GHSA-gjv8-xp57-g29c)
and [whitespace/comment advisory](https://github.com/facelessuser/soupsieve/security/advisories/GHSA-j934-xhv5-fg8f)
precedes the release. Source comparison confirms the later leading-identifier
quantifier correction and anchored reverse trailing-trim implementation; the
released parser is not that failing HEAD.

The paired comparison uses the same Python **3.10.19**, Beautiful Soup **4.12.3**
and `html.parser`, with one fresh process and one uncached call per case. Four
input families at size parameters 1,000/2,000/4,000/8,000 run twice in reversed old/new
order, alongside nine semantic controls: **82 processes, 41 per version**.
Each process has a Windows Job limit of 8 seconds user CPU, 256 MiB committed
memory and one active process, plus a 12-second outer wall limit. All 41 new
cases complete with expected results/exceptions. The eight old unterminated
attribute cases retain five wall timeouts and three nonzero/process-limit exits;
other old identifier, whitespace and
comment measurements show the retained input-size scaling. Normal result IDs,
document order, duplicates, escapes and syntax exceptions are checked separately.
The committed tests independently give **4 FAIL / 13 PASS on 2.8** and
**17 PASS on 2.9**, with bounded CPU/memory/wall resources. This is the evidence
for the two parsing fixes; audit absence alone is not used as proof.

Pinned uv **0.11.19** generated the two locks under the original controlled
build rules. Full comparisons of **404 root / 312 Docker package records**,
including sources, markers and dependencies, change only **Soup Sieve 2.8 -> 2.9**.
The two manifests pin `soupsieve==2.9`; the existing script regenerates constraints.
AnyIO 4.14.2, Beautiful Soup 4.12.3, Gradio 4.39.0, MCP 1.12.4, CPU torch and base
image digests remain unchanged. No canonical synchronization or full upgrade ran.
Both owned Windows environments received complete frozen installations. Version,
module path, seven official runtime-file hashes, non-editable installation and
dependency checks pass on Python **3.10.19 / 3.11.15**.

### Functional checks and actual products

HTML/MHTML readers, selector order/attributes/Unicode/escapes/pseudos/comments,
XML namespaces, malformed-selector exceptions, and the existing MCP HTML boundary
pass. Each Windows environment again passes **20 related tests** after receiving
the four verified CI wheels; `MARA` and `MARA-cli` help also pass. A separate
installed arXiv HTML consumer probe uses mocked HTTP and checks title/Unicode,
existing-file bytes and cleanup on both versions. Its initial repository fixture
pulled in five existing Windows `os.pread`/`os.fchmod` mypy errors; that new fixture
is retained in task evidence and the consumer probe runs outside the repository
test module. Original mypy configuration and import-following options are unchanged.

Complete Linux suites pass: root **1822**, ktem **3989**, kotaemon **512 PASS /
10 skipped on each Python version**; unified collection finds **6662 tests**.
Complete Windows kotaemon suites each retain **4 FAIL / 485 PASS / 33 skipped**:
the same FIFO and three symlink-privilege failures recorded previously. These
are not full Windows PASS results. Full Windows mypy's historical platform
limitations remain separate. Static/hygiene, original lock/constraints/CPU checks,
CLI, frontend/browser checks, four clean-wheel installations and Python
distribution supply-chain checks pass.

[Quality 37217372654](https://github.com/262412/MARA/actions/runs/37217372654)
completes with **13 success / 7 failure**. The seven failures are the three
Python audits, three container vulnerability gates and required aggregate.
Both secret-scan jobs pass: repository history covers **1536 commits**, the
full directory scan also passes, and the separately built image passes under
the unchanged 20-minute scanner / 45-minute job limits. Its actual image ID is
`sha256:512a762825396e100663d93fad7a57e45374e96636f5f5db7b10ab88627068d7`.

**Fresh coverage: PASS.** Artifact **11310460069**, from this run, yields
**90.22% / 81.93% / 72.20% / 84.40%** against unchanged benchmark / slide_cli /
kotaemon / ktem floors **90/70/60/50**. The original 90% production diff gate
passes at **96.60% (2642/2735 statements)** against fixed Dev `adab3f4d`.
Independent checks use the downloaded complete JSON and reproduce that result.
The batch-start diff against `9fea61ac` is **0/0, N/A**, since no production
Python statements changed; it is not reported as 100% architectural coverage.
No old coverage artifact substitutes for this run's results.

Python artifact **11308618776** contains four wheels and four sdists. All eight
payload hashes, SPDX/CycloneDX files and source/run-bound provenance were verified.
[Native 37217376092](https://github.com/262412/MARA/actions/runs/37217376092)
is a fresh **3/3 PASS** run, with Windows/Ubuntu 22.04 builds and Ubuntu 24.04
execution. Windows artifact **11308179487** and Linux artifact **11308734388**
match downloaded digests; all seven embedded Soup Sieve modules match code compiled
from official 2.9 source, excluding source filenames, and the parser differs from 2.8. Executed sidecar hashes
match those binaries. Defender reports no detections. Original resource probes
report no identified owned processes left running and no invalid package links,
while retaining **15 Windows / 152 Linux unclassified access-denied observations**.

All three new containers pass their original runtime and PCRE2 probes. Complete
OS/Python/Node/Go version inventories compared with batch 2's actual `6823a77a`
images change **only soupsieve, 2.8 -> 2.9**. PCRE2 remains **10.42-1+deb12u2**,
and its loaded-library hash still equals the signed Debian package. Trivy
**0.70.0** JSON, runtime image IDs, build metadata and OCI provenance agree:

| Target | Actual image ID                                                           | Artifact    | Trivy scan time, 2026-10-04 UTC |
| ------ | ------------------------------------------------------------------------- | ----------- | ------------------------------- |
| lite   | `sha256:1e9b848fbac2c2edacb1d4bfdccc519b63ee57a47f62a91d1a6dacd2146ba4ca` | 11309118216 | 16:48:57.617596284              |
| full   | `sha256:3bd0ec70b68de51b5cea24371260fd24c0e19aa13281919cf09ace8057b5bc14` | 11308334293 | 16:49:16.195180338              |
| ollama | `sha256:ef0d47eb3fc747815be8974135bea4aaa06c6e7727ad2f29ffb65dc37c714d65` | 11308894682 | 16:52:35.133372117              |

The original CI container gates fail with the same **12 exact new keys per
target**, covering Gradio, pypdf, sentence-transformers and urllib3. Two older
Soup Sieve baseline CVEs, **49476/49477**, also disappear; these are distinct
from this batch's independently reproduced **86000/85999**. The original
HIGH/CRITICAL fixable-only scan does not establish the two moderate parsing fixes.
Separate image SPDX/CycloneDX steps are not reached after enforcement fails.
Baseline expiry remains **2026-10-04**. CI enforcement actually ran on October 4
UTC; local unchanged-gate executions on October 5 CST each fail closed with
**exit 2, baseline expired**. No date override or extension was used.

All three fresh Python audit profiles retain complete raw uv JSON and actual
argv/env/cwd. Raw records number **433 / 433 / 410**, active records
**417 / 417 / 402**, and exact new baseline keys **47 / 47 / 39**. Relative to
retained batch-1 raw JSON, eight Soup Sieve record keys disappear and none are
added; those keys represent four CVE alias groups, not eight vulnerabilities.
The two target advisories and PYSEC-2026-4170/4171 account for four removed new
keys. The other four removed records are incidental older findings, not extra
independently reproduced fixes. Baselines, alias handling, scope and gates remain
unchanged. The historical missing audit/log evidence remains missing.

### Retained attempts, protection and review boundary

Failed attempts remain separate: initial hook bootstrap restrictions; empty
metadata response; the first process launcher failing before parsing; an initial
lock-comparison uniqueness assumption; a wrong test selection; supplemental
arXiv fixture whitespace/type-platform failures; the Python 3.11 root test's
existing unconditional `tomli` import; CRLF diff-check false positives; and an
image comparison that incorrectly assumed resolved baseline keys were unchanged.
Corrections preserve the original scanner, type-check and baseline contracts.
The task-owned failure index also retains expected old-version/type-error reds,
all Windows capability failures and security-gate failures.

The **135 historical**, **136 preceding-round opening user changes**, and
**136 current-round opening user changes** are checked by path and hash as
separate sets, together with NUL. Newly appearing paths are compared separately.
The two observed primary mypy files retain their post-incident hash and mtime;
their unknown preimage is not reconstructed. Canonical installation, real data,
configuration/cache and the eight historical UV directories were not synchronized,
cleaned, restored or rescanned. U1 and dual-37 were not run as prerequisites.

Raw evidence is under `D:/MARA-s1-01a086ff/s1-soupsieve-20261004/`.
`evidence/batch-evidence.json` and `evidence/evidence-source-index.json` bind
release/source hashes, actual invocations, independent attempts, protection sets,
coverage, audits and downloaded products. The October 5 acceptance is limited
to the separate scopes above; unresolved gates retain **NO-GO**.

## Accepted S1 PCRE2 batch 2 measured scope (2026-10-04)

**The user's October 4 independent review separately ACCEPTS batch 2's measured
PCRE2 linux/amd64 scope and exact Gitleaks public-tag exception.** The large
32-bit converter overflow was not exercised. The user's acceptance
of AnyIO batch 1 is limited to its agreed implementation and measured scope.
R6-D remains **BLOCKED / not ACCEPTED**, historical protection and U1 dispositions
remain OPEN/deferred, and merge/release remains **NO-GO**. Batch 3 is recorded above.

The branch remains `codex/r0-r1-safe-refactor`, starting at
`3ad48d9b2d43c94624e982ad132e0255410b56c9`. Separate ordinary commits are:

- Exact public-tag exception: `12740fef74c65796588723ca6a224b09b0d325fd`.
- Runtime PCRE2 pin and bounded checks: `cf3e1c26697d19ae822bb84f97901be943048385`.
- Slim-image documentation verification correction and final execution source:
  `6823a77a9e01e3970cc7dccf36aec741856146d5`.

### PCRE2 package, runtime and image evidence

Only the existing `runtime-base` apt list gains
`libpcre2-8-0=10.42-1+deb12u2`. Base-image digests, both Python locks, constraints,
AnyIO 4.14.2, Soup Sieve 2.8 and other dependency declarations are unchanged.
Preflight verified the pinned base's Bookworm apt sources and archive keyring,
the signed security InRelease (valid October 4-11 UTC), its Packages checksum,
the amd64 package and dependency/reverse-dependency constraints. This was a
signed-metadata check, not a local apt simulation. The new CI builds then
executed the actual apt installation through the original sources.

The verified `.deb` SHA-256 is
`d2f7edfcc7689b9e0761c2742cc824ac86a20768bc5e8057818dc6875291fe76`.
All three final containers report binary/source version **10.42-1+deb12u2**,
architecture **amd64**, correct dpkg ownership and the loaded library
`/usr/lib/x86_64-linux-gnu/libpcre2-8.so.0.11.2`. Its SHA-256 is
`092bc945140e65c691c7c717d71083111f46813f31a76dd848bf82e91450778b`, identical
to the signed package. `/proc/self/maps` and grep's dynamic linkage resolve to
that library. Full OS/Python/Node/Go version inventories compared with accepted
AnyIO candidate `8aa37359` change **only libpcre2-8-0, 10.42-1 -> 10.42-1+deb12u2**.

| Target CVE      | Evidence on each new amd64 image                                                                          |
| --------------- | --------------------------------------------------------------------------------------------------------- |
| CVE-2026-86145  | Fixed package/library plus bounded DFA heap-limit regression, expected -63                                |
| CVE-2026-89157  | Fixed package/library plus small converter smoke; the large 32-bit overflow is **not exercised** on amd64 |
| CVE-2026-89161  | Fixed package/library plus copied-subject reuse/free regression                                           |
| CVE-2026-103111 | Fixed package/library plus bounded JIT recursion regression, expected -46                                 |

[Debian's DLA-4816-1 record](https://security-tracker.debian.org/tracker/DLA-4816-1)
and the four CVE records identify the fixed Bookworm boundaries; u2 includes 103111. The original container smoke, grep check and three bounded regressions
pass on every target. Each probe has a 30-second outer timeout and inner
CPU/address-space limits. The package verification permits only the three exact
documentation files excluded by the unchanged slim-image dpkg configuration;
missing library/copyright or modified-file rows still fail. Raw verification
output, full installed-package lists and failure-output tests are retained.

All following artifacts belong to **Quality 37209618859, attempt 1, source
6823a77a**. Full Trivy **0.70.0** JSON, probe stdout/stderr, build metadata and
provenance are retained. Downloaded ZIP hashes match GitHub metadata; the runtime
image IDs match Trivy, and provenance binds the source/run and OCI subjects.

| Target | Actual image ID                                                           | Artifact    | Trivy scan time, 2026-10-04 UTC |
| ------ | ------------------------------------------------------------------------- | ----------- | ------------------------------- |
| lite   | `sha256:ddac91ee48896d7c185a299a5ea23b28133bb298da4bf2f40c59a3d242eb5118` | 11306360764 | 14:42:59.290276472              |
| full   | `sha256:b4bedc474c1ad2778c3ec40668e706016dbdfdc8a3c74e9fbee15dfa4c66a9e6` | 11306356880 | 14:45:46.450908264              |
| ollama | `sha256:9f6d40cbb93314593a6f226a48a40af627c9bab516b5c425e4272bd43fd16e04` | 11306491985 | 14:49:47.009058631              |

No PCRE2 finding remains in these JSONs. Each original-parameter container gate
still fails on **12 exact new keys**: Gradio (1), pypdf (8), sentence-transformers
(1), urllib3 (2). These are not unique-vulnerability counts. The unchanged
baseline expires on **2026-10-04**; actual scan/enforcement dates were October 4
UTC, with no date override or extension. Separate image SPDX/CycloneDX steps
were **not reached** after enforcement failed.

### Exact public-tag exception and Quality

The real Gitleaks 8.24.3 match includes the complete public tag followed by the
Markdown closing backtick. A separate `generic-api-key` rule allowlist requires
**AND** between the exact report path and the anchored complete match. The
original G0 block remains byte-for-byte intact. No file/commit/general-SHA
exception, disabled rule or vulnerability-baseline change is introduced.

Fresh controls from the final Git archive pass **38/38** across history and
directory modes: the exact public case, changed value/path/context/prefix,
other and same-line dummy credentials, and original G0 positive/negative cases.
The new CI repository/history job passes both **1,533-commit history** and full
`/repo` directory scans. A local Windows directory attempt's six known QASPER
fixture-hash hits remain recorded: its relative paths do not match the existing
`/repo` ignore fingerprints; the ignore file was not changed. The independent
built-image secret scan also passes its original 20-minute scanner/45-minute
job budgets, using image ID
`sha256:fb717b8278122d1e7ff73fb2249e372ae4caf6eb01be027eed4a1477d1371ead`.

[Final Quality 37209618859](https://github.com/262412/MARA/actions/runs/37209618859)
completed with **13 success / 7 failure**. Failures are the three Python audits,
three container vulnerability gates and required aggregate. Functional results
include root **1822 PASS**, ktem **3989 PASS**, kotaemon
**495 PASS / 10 skipped on each Python version**, and collection of **6645 tests**.
CLI, static/hygiene, frontend/browser checks, four clean-wheel installations
and distribution supply-chain checks pass. Artifact **11306255788** contains
eight verified distribution hashes with source/run-bound provenance.

**Fresh coverage: PASS.** Artifact **11306787930** produces **90.22% / 81.93% /
72.20% / 84.40%** against unchanged benchmark / slide_cli / kotaemon / ktem floors
90/70/60/50. The original 90% production diff gate passes at **96.60%
(2642/2735 statements)** against fixed Dev `adab3f4d`. These numbers use the
new run's complete coverage JSON, not the first attempt or batch-1 coverage.
Local final targeted checks pass **45 tests** with one existing POSIX-only case
deselected on Windows; Linux root CI covers the full container-test module.

The three fresh Python audit logs fail with **51 / 51 / 43 exact new keys**;
CI does not upload complete uv audit JSON. Earlier batch-1 complete JSON remains
historical evidence and is not relabeled as a new execution.

Actual Desktop build-input Git blobs are unchanged from `8aa37359`, including
the desktop build/bundle scripts, library trees, root manifest/lock and
Native workflow. [Native 37194425712](https://github.com/262412/MARA/actions/runs/37194425712)
**3/3 PASS** is therefore reused as historical evidence at that SHA, not a new
Native execution. U1 and dual-37 were not started or used as prerequisites.

### Retained failures and protection limits

[Initial Quality 37206187450](https://github.com/262412/MARA/actions/runs/37206187450)
at `cf3e1c26`, attempt 1, completed naturally with **13 success / 7 failure**.
All three runtime probes reached an overly strict empty `dpkg --verify` output
assertion; Trivy did not run and no Trivy JSON exists for those attempts. The
first assertion did not emit its inner command output, which remains missing.
The exact slim-documentation correction has positive/negative tests; the final
run's three explicit missing-documentation rows do not reconstruct the first
output. Both complete runs and all named local failed attempts are retained.
The earlier AnyIO overwritten-log gap also remains explicitly missing.

**A new protection incident remains OPEN.** Hook attempt `gitleaks-hooks-02` wrote
the primary checkout's `.mypy_cache/3.10/scripts/supply_chain_contracts.data.json`
and `.meta.json` at 13:22:02 UTC. There is no initial cache preimage and no claim
that these are the only cache writes. Their originals were not restored,
deleted or given changed mtimes. Subsequent hooks explicitly route mypy,
Black, Ruff, pip and other caches into the task-owned directory; the two observed
files have not changed since that correction. This verifies forward routing,
not historical cache integrity. The 135 protected hashes, 136 opening user-change
hashes and NUL remain separately guarded. Canonical installation and the eight
historical UV directories were not synchronized, cleaned, restored or rescanned.

Raw evidence is under `D:/MARA-s1-01a086ff/s1-pcre2-20261004/evidence/`.
`final-container-comparison-01.json` binds complete old/new inventories, original
target findings, current findings, runtime evidence and artifact identities.
The final `batch-evidence.json` and `evidence-source-index.json` link the
independently named attempts and selected raw file hashes. This report's final
documentation-only commit follows the verified `6823a77a` execution source.

## Accepted S1 AnyIO batch 1 measured scope (2026-10-04)

**AnyIO batch 1 is ACCEPTED within its agreed implementation and measured
scope following the user's independent review on 2026-10-04.** All recorded
failures, evidence gaps and platform limits remain. R6-D overall remains
**BLOCKED / not ACCEPTED**, remaining S1 gates stay OPEN, and merge/release remains
**NO-GO**.

This batch starts at `9d597d772c2b90d4b2e9598312f536533585f7ee` on
`codex/r0-r1-safe-refactor`. The frozen execution candidate is
`8aa3735931fb79141b76f3e000de56e1910758b0`. Its changes are the five synchronized
dependency files, three bounded security test cases, and one exact-constraint
expectation updated to include the new pin. Root and Docker lock comparisons
cover all 404 / 312 package records: **only AnyIO changes, 4.11.0 -> 4.14.2**.
Gradio 4.39.0, MCP 1.12.4, Python ranges and CPU torch remain unchanged. Existing
MCP adapters, loop-policy behavior and public MARA/CLI contracts are retained.

Resolution and installation used pinned uv 0.11.19 with explicit Python,
cache, temporary and environment paths in the task-owned full source copy.
Build isolation remained enabled. Alongside four first-party projects, only
six already-locked sdist-only inputs were admitted after inspecting their exact
digests and build entries: html2text, langdetect, llama-cpp-python, pypika,
umap-learn and wikipedia. The source archive's real backend initially produced
first-party version 0.0.1; final CI builds with Git history produced 0.0.40.
Both Windows candidates first received full frozen-lock installations, then
the four verified CI wheels. The later `--no-deps` replacement is not the
third-party dependency upgrade. Dependency checks pass for 371 / 370 installed
packages on Python 3.10.19 / 3.11.15, including AnyIO 4.14.2 at verified paths.

### Current execution evidence

All final CI entries below use candidate `8aa37359`, attempt 1:

- [Quality 37194846821](https://github.com/262412/MARA/actions/runs/37194846821):
  **12 success / 8 failure**. All functional and full coverage checks pass;
  remaining failures are the three Python audits, three container vulnerability
  gates, repository/history secret scan and required aggregate. Functional results include
  benchmark/root **1806 PASS**, ktem **3989 PASS**, and kotaemon **495 PASS /
  10 skipped on each of Linux Python 3.10 and 3.11**. CLI, collection of 6629
  tests, static/hygiene, lock/constraints/CPU parity, four clean-wheel installs
  and distribution attestations pass. Frontend tests **40 PASS**, browser
  security checks **8 PASS**; these do not start or close U1 or dual-37.
- Windows Python 3.10 / 3.11 each pass **129 MCP, CLI and security tests** after
  installing the final CI wheels. Coverage includes Selector callers, the
  Proactor bridge, repeated cancellation, all-task shutdown, owned worker
  thread/process completion and subsequent calls. Business exception and call
  count contracts remain unchanged.
- The new bounded regressions use an owned process with >2 MB stderr and a
  loopback server with temporary certificates. All **three cases fail with
  installed AnyIO 4.11.0** and pass with 4.14.2: worker progress/cleanup, correct
  Unicode/IDNA certificate acceptance and rejection of the legacy-mapped name.
- [Native 37194425712](https://github.com/262412/MARA/actions/runs/37194425712):
  **3/3 PASS**, including fresh Windows and Ubuntu 22.04 packages, Ubuntu 24.04
  execution and Windows Defender with no detections. Downloaded archive digests
  match GitHub metadata. Each frozen sidecar's 35 embedded AnyIO modules match
  code compiled from the official 4.14.2 wheel sources (excluding source
  filenames); the TLS module does not match 4.11.0.
  `anyio.to_process` is not bundled; its security regression uses the complete
  installed environments. Executed sidecar hashes match the downloaded packages.
  Resource probes report no remaining identified owned processes or invalid
  package links, retaining **13 Windows / 150 Linux unclassified access-denied
  observations** rather than claiming visibility into every host process.

**Fresh coverage: PASS.** Artifact **11301930471**, generated by the final
run, passes unchanged floors 90/70/60/50 with **90.22% / 81.93% / 72.18% /
84.40%** for benchmark / slide_cli / kotaemon / ktem. The unchanged production
diff gate also passes at its original 90% threshold:

| Base                         | Covered / changed statements | Result                                       |
| ---------------------------- | ---------------------------- | -------------------------------------------- |
| Fixed Dev `adab3f4d`         | 2640 / 2735                  | 96.53%                                       |
| R6-D increment `bef108c6`    | 32 / 33                      | 96.97%                                       |
| Limited R6-C `f8a57979`      | 32 / 33                      | 96.97%                                       |
| Accepted scope `5474ec2c`    | 32 / 33                      | 96.97%                                       |
| AnyIO batch start `9d597d77` | 0 / 0                        | N/A: no changed production Python statements |

These checks use the downloaded final `coverage.json`; package scope, omit rules
and thresholds are unchanged. The script prints 100% for an empty diff, but the
0/0 batch result is not reported as architectural coverage. No earlier candidate
or historical f5 coverage substitutes for this run.

Final Python artifact **11299934840** contains four wheels and four sdists;
all eight hashes, SPDX/CycloneDX records and provenance bind to `8aa37359`.
Final Native package artifacts are **11300149206** (Windows) and **11299944690**
(Linux). Their complete identities are retained in the machine evidence below.

### Actual images and remaining security gates

All three new runtime images build and pass their existing smoke checks. Full
Trivy 0.70.0 JSON inventories contain AnyIO **4.14.2**, with no AnyIO finding.
Their Python version inventories differ from the September 28 images only for
AnyIO. Each OS inventory additionally changes **libexpat1
2.5.0-1+deb12u3 -> 2.5.0-1+deb12u4** through the unchanged apt build steps.
PCRE2 remains **10.42-1**; the images are not claimed to differ only in AnyIO.

| Target | Actual image ID                                                           | Artifact    | New exact keys |
| ------ | ------------------------------------------------------------------------- | ----------- | -------------- |
| lite   | `sha256:d9ea9284ce7dac7a399a3b0873ff7db86465a9aa71ec30b9b1928ea171c561dc` | 11301080839 | 16             |
| full   | `sha256:afcbca93685373a69fec75c6a597f6f5e1d3ce8260220bd31fec167d58ff393b` | 11301091094 | 16             |
| ollama | `sha256:a5d4136d8cb81514795401d03f151701f5adfb2639499dadf7f9bcb9c090b3e4` | 11300502364 | 16             |

The scans ran on 2026-10-04 UTC. `expires_on=2026-10-04` remains unchanged;
these failures are new findings, not an expiry override. The 16 keys per target
cover Gradio (1), PCRE2 (4), pypdf (8), sentence-transformers (1) and urllib3 (2).
Separate image SPDX/CycloneDX outputs are **NOT PRODUCED**: their steps follow
the failed enforcement. Raw Trivy JSON, build metadata and provenance are saved.

Python audit gates fail with **51 / 51 / 43 exact new keys** for root-py310,
root-py311 and container-py310. Complete JSON from the task-owned executions
using the same pinned tool, locks and profile flags agrees with final CI's
emitted keys; CI itself does not upload its complete uv JSON. The six original
Python AnyIO rows and three original container TLS rows are reconciled against
actual installed versions, current aliases and the official 4.14.2 fixed boundary.
Extra exact keys include aliases of earlier records and are not unique-vulnerability
counts. The missing original September 28 Python JSON remains missing; new data
does not reconstruct it. Baselines, alias handling and scanner rules are unchanged.

The current [built-image scan](https://github.com/262412/MARA/actions/runs/37194846821/job/111414469894)
completes successfully under the unchanged 20-minute Trivy / 45-minute job
budgets and finding-exit contract. No secret finding rows are emitted. Its
independently built lite image has local ID
`sha256:33df1a68482adf6ea76439fc62f9a89bff2a9cf46bd704f851506dca75384ca6`;
this differs from the vulnerability-scan image above. The scanner action ran
for 188,368 ms, ending at 10:23:23 UTC. The repository/history job remains
**FAIL**: the `generic-api-key` rule matches the earlier report's public image
tag containing commit 4203ca87, introduced in 257a3dc9. That failure is retained;
no suppression, history rewrite or rule change is included.

### Retained failures, protection and review boundary

Initial [Quality 37193383944](https://github.com/262412/MARA/actions/runs/37193383944)
at `5b982ac9` remains **10 success / 10 failure**. Root and coverage encountered
one stale exact-set expectation; the one-line fix was reproduced red and then
green before freezing `8aa37359`. Initial coverage stopped in its first suite;
its raw logs and partial artifact remain separate from the final run. An early
bounded lock attempt's log filenames were accidentally reused; its known
failure is recorded as an observation with the missing raw-log limitation,
not a recovered original. Other diagnostic failures and successful retries are
retained in the task evidence.

The 135 protected hashes, starting user content and NUL match the opening
snapshot. Canonical installation, real configuration/DB/cache and the eight
historical UV directories were not synchronized, cleaned, restored or rescanned.
Historical integrity/disposition remains OPEN. Prior R5/R6-B/R6-C and limited
P-UV/DL-POSIX acceptances, the accepted earlier image scan and deferred U1 remain
separate. No later S1 batch starts here.

Machine evidence is under `D:/MARA-s1-01a086ff/s1-anyio-20261004/evidence/`:
`batch-evidence.json` links original/current finding identities, complete audit
inputs, invocations, failures and actual artifact records; `final-source-identity.json`
retains the five-file patch and full lock comparison.
`final-coverage-verification.json` records the fresh floors and all five base
checks; `evidence-source-index.json` records selected evidence file hashes and
artifact metadata. The final documentation-only commit follows the verified
`8aa37359` execution source and is not represented as another CI-tested build.

## Retained R6-D review and S1/PCRE2 remediation plan at 9d597d77 (2026-10-04)

**The user accepts the new-image secret-scan evidence below within its limited
review scope. R6-D overall remains BLOCKED / not ACCEPTED; merge/release remains
NO-GO.** This planning round starts at
`257a3dc92bd7b3d57916cf5cbd98cd8520539d97` and changes documentation only.
The user-provided review outcome separately accepts **P-UV forward installation**
and the **DL-POSIX controlled lifecycle contract** within their limited scope.
Their execution evidence remains dated 2026-09-28 at source
`f5d974ce4183eb9e618da49bab5499505029fcb0`; neither repair was reimplemented or
rerun here. This acceptance does not close historical protection incidents or
establish the unique interleaving of the original POSIX failure. Prior structure
contracts/documentation and R5/R6-B/R6-C acceptance remain unchanged.

The earlier scan change started at `64036ff380af170e20a5f9e996b36c79acd6e9f1`. Its pushed
commit `4203ca87cf7f62a84878d231014925e9e90502ce` changes exactly two workflow
fields: Trivy image `timeout: "20m"` and image job `timeout-minutes: 45`.
Semantic comparison confirms every other field is identical. The pinned action
`aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25` retains
Trivy v0.70.0, `scanners: secret`, `exit-code: "1"`, the lite target, existing
rules, cache policy, permissions and failure propagation. No skip/ignore,
dependency-directory exclusion or continue-on-error was added.

Earlier 2026-10-04 image-scan workflow checks: the release-containment, workflow and
supply-chain suites passed **56 tests before and 56 after** the two-line change;
the supply-chain policy, YAML validation and formatting checks passed. Checks
used the existing task-owned environment and hook binaries without installing
anything. No full Quality, Native, package installation or business suite was
redispatched. No automatically triggered gate was cancelled.

[Secret Scanning 37177161966](https://github.com/262412/MARA/actions/runs/37177161966),
**attempt 1**, was dispatched once at workflow/source SHA
`4203ca87cf7f62a84878d231014925e9e90502ce`; both jobs succeeded:

- [Built image, job 111362084132](https://github.com/262412/MARA/actions/runs/37177161966/job/111362084132):
  normal completion, scanner exit **0**, no secret finding records. The Trivy
  substep ran from 04:33:03 to 04:35:49 UTC on 2026-10-04, reporting 166,447 ms.
  The complete table and successful action termination are in this job log;
  its 392,340 raw bytes have SHA256
  `0e76bc9e71f9dee575d230f9d89fd66b5f796abde76c1d96dc8088b02fef179c`.
- [Repository and history, job 111362084262](https://github.com/262412/MARA/actions/runs/37177161966/job/111362084262):
  Gitleaks completed 1,524 commits and the current worktree with no leaks found.
  Raw job-log SHA256:
  `6cee4977d819eb9ae3a58399db24fb991a72d2281cc8a4c9d54692d7194d1a85`.

The image build ran from 04:29:56 to 04:33:02 UTC on the Ubuntu 24.04 Linux X64
runner. Its actual local image ID is
`sha256:13c772bbad9a4e8f59559dabe208058c1e55a17c0050e877617d2ae8e3cc89a7`.
The build log assigns that ID to
`mara-secret-scan:4203ca87cf7f62a84878d231014925e9e90502ce`, and the immediately
following command scans that same tag. No registry publication or RepoDigest
was produced. The original image was not among the available saved artifacts;
this is a new build, not a byte-equivalent re-scan of the old image
`sha256:5a6170f7e8de7152431aa051d0188eda1cba00007ebd8bbd587ea519a5b6db1b`.

The recorded invocation is `trivy image mara-secret-scan:<4203ca87 full SHA>`.
The [fixed action](https://github.com/aquasecurity/trivy-action/blob/ed142fd0673e97e23eac54620cfb913e5ce36c25/action.yaml)
maps the logged `INPUT_TIMEOUT=20m`, `INPUT_SCANNERS=secret`
and `INPUT_EXIT_CODE=1` into the scanner environment. Setup selected v0.70.0 and
restored `trivy-binary-v0.70.0-Linux-X64`; the existing workflow does not emit a
separate binary hash. The complete summary contains 409 package rows marked
`-`, meaning not applicable to the secret result class, not 409 zero findings.
The [v0.70.0 summary semantics](https://github.com/aquasecurity/trivy/blob/v0.70.0/pkg/report/table/summary.go)
emit secret result rows only for findings; the completed command returned no
such rows. This is an execution result under the unchanged rules,
not proof of per-file coverage or the unique cause of the old timeout.

Business/package/test inputs are unchanged from f5: only this report and the
workflow differ. The original Dockerfile and locked build inputs are retained.
Their SHA256 values at the executed SHA are:

- `Dockerfile`: `96627818b7c9ead5d6490ecfa5a8167170b2ae67c1307f3ca547b831133f982e`
- `.dockerignore`: `45615ef7f30f35f2373d8c246b198f6be7ca717a0f1e1069be6a1105e35fa583`
- `uv.lock`: `245678ee0ec3d7ddf2ad32817f806baa19d61ed1fadf41a646730bb902c5679b`
- `docker/uv.lock`: `0291c503644c7980395d7f3e5e409f7d4b96d603aa8be458b6ac3852c4789817`

The Python base remains `python:3.10.20-slim-bookworm` at
`sha256:ff7161e2b8e2a56fc6a62a6099ff8feb72f1a6dbae9860cdcb9a6c65cf4c6be9`.
Base/tool image and build-layer identities remain visible in the complete build
log. The new image ID, rather than Git equivalence alone, identifies this scan.

Original Quality **36428131096, attempt 1, remains 12 success / 8 failure**.
Its image job **108948912840** timed out before completion; it remains
INCOMPLETE, neither a detected-secret finding nor a zero-findings PASS. The new
independent result does not rewrite that job or its failed required aggregate.
The existing six dependency/container failures and S1/PCRE2 remain OPEN.

Current read-only checks confirmed the same 135 protected file hashes and NUL;
no additional user content changes were found. The canonical environment,
private configuration/DB/cache and eight UV incident directories were not
installed into, cleaned, restored or timestamp-adjusted. Their full metadata
and 1,022-file hash evidence below belongs to **2026-09-28** and was not repeated
here. Historical UV/configuration/cache integrity and disposition remain OPEN.

The scan's limited review is now accepted. Remaining work is S1/PCRE2
remediation, historical protection owner disposition, U1 in its deferred lane,
and the already recorded platform/product limits. No new structure phase,
Login/dual-37 campaign, dependency implementation, merge or release starts here.

### Planning evidence and original finding identities

This is a plan against the **2026-09-28** Quality findings, using current official
advisory/package metadata queried on **2026-10-04**. No fresh whole-profile audit,
Quality/Native dispatch, three-image build or business acceptance was performed.
The original 14 emitted Python findings in each of `root-py310`, `root-py311`,
`container-py310`, and four in each of `lite`, `full`, `ollama`, remain separate
rows: **42 Python profile rows + 12 container target rows**. These are deltas
against frozen legacy baselines, not total vulnerabilities or a current rescan.

Both gates compare exact `package==version|ID` identities; neither imports an
alias normalizer. The following official alias relationships are analysis only.
Each Python row occurs in all three original profiles; the machine ledger keeps
all rows, job IDs, log hashes, versions, provenance and full source responses.

| Original ID                                                             | Original package/version | Confirmed CVE / GHSA relationship                               | Official repair threshold                                      |
| ----------------------------------------------------------------------- | ------------------------ | --------------------------------------------------------------- | -------------------------------------------------------------- |
| [GHSA-5p39-cfhj-2xmp](https://api.osv.dev/v1/vulns/GHSA-5p39-cfhj-2xmp) | anyio 4.11.0             | CVE-2026-64847                                                  | 4.14.2                                                         |
| [GHSA-82r6-8w77-94w6](https://api.osv.dev/v1/vulns/GHSA-82r6-8w77-94w6) | anyio 4.11.0             | CVE-2026-63374; same advisory as the three container AnyIO rows | 4.14.2                                                         |
| [PYSEC-2026-3813](https://api.osv.dev/v1/vulns/PYSEC-2026-3813)         | chromadb 0.5.16          | CVE-2026-45830 / GHSA-2wm9-hf6c-p5cr                            | No patched release; last affected 1.5.9                        |
| [PYSEC-2026-3814](https://api.osv.dev/v1/vulns/PYSEC-2026-3814)         | chromadb 0.5.16          | CVE-2026-45833 / GHSA-36p7-vc44-83pf                            | No patched release; last affected 1.5.9                        |
| [PYSEC-2026-3815](https://api.osv.dev/v1/vulns/PYSEC-2026-3815)         | chromadb 0.5.16          | CVE-2026-45831 / GHSA-xph7-9rjv-w5fr                            | No patched release; last affected 1.5.9                        |
| [GHSA-8mgp-746c-j5xp](https://api.osv.dev/v1/vulns/GHSA-8mgp-746c-j5xp) | nltk 3.10.3              | CVE-2026-81726                                                  | No patched release; last affected 3.10.3                       |
| [PYSEC-2026-3910](https://api.osv.dev/v1/vulns/PYSEC-2026-3910)         | pypdf 4.2.0              | CVE-2026-84310 / GHSA-23w6-3w8w-8484                            | 6.16.1                                                         |
| [PYSEC-2026-3911](https://api.osv.dev/v1/vulns/PYSEC-2026-3911)         | pypdf 4.2.0              | CVE-2026-84311 / GHSA-763m-79hh-57f2                            | 6.16.1                                                         |
| [PYSEC-2026-3912](https://api.osv.dev/v1/vulns/PYSEC-2026-3912)         | pypdf 4.2.0              | CVE-2026-82398 / GHSA-fc8x-2rww-xw9m                            | 6.15.0                                                         |
| [PYSEC-2026-3913](https://api.osv.dev/v1/vulns/PYSEC-2026-3913)         | pypdf 4.2.0              | CVE-2026-84309 / GHSA-jp53-mhqp-8xcg                            | 6.16.0                                                         |
| [GHSA-gjv8-xp57-g29c](https://api.osv.dev/v1/vulns/GHSA-gjv8-xp57-g29c) | soupsieve 2.8            | CVE-2026-86000                                                  | 2.9.0, published as 2.9                                        |
| [GHSA-j934-xhv5-fg8f](https://api.osv.dev/v1/vulns/GHSA-j934-xhv5-fg8f) | soupsieve 2.8            | CVE-2026-85999                                                  | 2.9.0, published as 2.9                                        |
| [PYSEC-2026-3929](https://api.osv.dev/v1/vulns/PYSEC-2026-3929)         | transformers 4.56.2      | CVE-2026-9856 / GHSA-xrqw-3rrv-vx5w                             | 5.10.0; that release is yanked, select 5.10.1 as repair target |
| [PYSEC-2026-3930](https://api.osv.dev/v1/vulns/PYSEC-2026-3930)         | unstructured 0.15.14     | CVE-2026-71428 / GHSA-4mvj-m6j5-pmf7                            | 0.24.0                                                         |

The Python comparison logs did not retain the complete `uv audit` JSON or an
advisory database revision; current OSV responses do not reconstruct those
missing historical fields. Container artifacts do retain complete Trivy JSON
(version 0.70.0), package inventories and provenance, but no database digest.
The separate SPDX/CycloneDX steps after failed enforcement did not produce
saved artifacts. Build-time SBOM configuration is not evidence of those files.

### Active Python chains, candidates and compatibility limits

The three audit profiles use Linux x86_64, `--frozen --no-dev`, Python 3.10/3.11
as named, and the application's `kotaemon[mara-runtime]` dependency. The
container project additionally includes `mara-research-cli` and CPU torch 2.8.0.
The existing `uv tree` output also displays workspace extras; analysis follows
only root dependencies, selected extras and true markers. `active-graphs.json`
contains every selected edge and the complete path through every direct parent
of each affected package. All seven affected versions are active in all three
profiles. No inference of Windows/macOS execution is made from a universal wheel.

In the chains below, `K` means `mara-app -> kotaemon[mara-runtime]`; the container
adds `mara-container-runtime -> mara-app`. Every Python implementation batch
must synchronize **`uv.lock`, `docker/uv.lock`, `constraints.txt`** together.
`constraints.txt` is generated by `scripts/sync_locked_constraints.py`, never
hand-edited. Regression paths below are existing tests to run after an authorized
upgrade; none was rerun for this plan.

- **AnyIO, batch 1: 4.11.0 -> 4.14.2.** Active paths after `K` are
  `gradio -> anyio`, `mcp -> anyio`, `mcp -> sse-starlette -> anyio`,
  `openai -> anyio`, `langchain-anthropic -> anthropic -> anyio`,
  `fastapi -> starlette -> anyio`, `chromadb -> httpx -> anyio`, and
  `chromadb -> uvicorn -> watchfiles -> anyio`; `ktem` supplies additional
  Gradio/MCP edges. Parent bounds are respectively `>=3,<5`, `>=4.5`, `>=4.7`,
  `>=3.5,<5`, `>=3.5,<5`, `>=3.4,<5`, unbounded and `>=3`.
  [4.14.2 metadata](https://pypi.org/pypi/anyio/4.14.2/json) satisfies all eight;
  its non-yanked `py3-none-any` wheel requires Python >=3.10. Existing idna 3.10,
  exceptiongroup 1.3.0 and typing-extensions 4.15.0 satisfy its requirements.
  No SDK, Gradio or MCP version change is planned. Add the exact AnyIO constraint
  to root and docker `pyproject.toml`; first-batch files/checks are detailed below.
- **Soup Sieve, batch 3: 2.8 -> 2.9.** `K -> beautifulsoup4 4.12.3 -> soupsieve`;
  its `soupsieve>1.2` requirement admits [2.9](https://pypi.org/pypi/soupsieve/2.9/json).
  This non-yanked universal wheel requires Python >=3.10 and has no dependencies.
  Add `soupsieve==2.9` to root/docker constraint-dependencies, keeping
  `beautifulsoup4>=4.12.3,<4.13`. Run
  `libs/kotaemon/tests/test_reader.py::{test_html_reader,test_mhtml_reader}`
  (the two node IDs separately) and `test_mcp_html_boundary.py`; add bounded CSS
  selector regression cases for both advisories. HTML input alone does not
  establish attacker control of CSS selectors. No solve or installation done.
- **pypdf, batch 4: repair target 6.16.1; blocked by the reader stack.** Direct
  `K -> pypdf` requires `>=4.2.0,<4.3`; `K -> llama-index 0.10.68 -> llama-index-readers-file 0.1.33 -> pypdf` requires `>=4.0.1,<5`.
  `K -> unstructured -> unstructured-client 0.25.9 -> pypdf` only requires >=4.0.
  [6.16.1](https://pypi.org/pypi/pypdf/6.16.1/json) covers all four rows and offers
  a non-yanked universal wheel for Python >=3.9. It has no solution inside the
  current first two caps. `libs/kotaemon/pyproject.toml` must coordinate pypdf
  with the llama-index family: readers-file 0.7.0 admits pypdf 6 but requires
  core >=0.13,<0.15, whereas the current umbrella requires core <0.11 and
  readers-file <0.2. That is a migration option, not a solved minimum set.
  Regress PDF loading, `libs/kotaemon/tests/test_loader_multimodal_figures.py`,
  `libs/ktem/ktem_tests/test_preview_pdf_core.py`, `test_preview_pdf_compatibility.py`
  and `test_docqa_element_sidecar_contract.py`; add bounded outline, XForm,
  whitespace and tree-object malformed-PDF cases. Preserve page/citation/error APIs.
- **Transformers, batch 5: repair target 5.10.1; blocked by model/UI coupling.**
  `K -> sentence-transformers 5.1.1 -> transformers` requires `>=4.41,<5`.
  The same cap remains in 5.1.2; checked 5.2.0 permits <6.
  [5.10.0 is yanked; 5.10.1 is non-yanked](https://pypi.org/pypi/transformers/5.10.1/json),
  with a universal Python >=3.10 wheel. It requires hub >=1.5,<2 and
  regex >=2025.10.22; tokenizers 0.22.1 already meets >=0.22,<=0.23.
  The original Gradio 4.39.0 wheel's `gradio/oauth.py:12` imports `HfFolder`,
  [removed from the Hub 1.x API](https://huggingface.co/docs/huggingface_hub/concepts/migration).
  Thus merely loosening sentence-transformers is insufficient. Coordinate its
  entries in `libs/kotaemon/pyproject.toml`, both lock inputs and an explicitly
  chosen Gradio-compatible route or official backport. No automatic UI upgrade
  or site-packages patch is proposed. Regress `test_embedding_models.py`,
  `test_retrieval_quality.py`, QASPER tokenizer/budget contracts and an offline
  real-model fixture; mocks alone cannot establish embedding/reranker parity.
  Add a local `save_pretrained` path-containment case. No full solve done.
- **Unstructured, batch 6: 0.24.0 is a Python 3.11 repair target, not a common
  3.10/3.11 candidate.** `K -> unstructured` declares `>=0.15.8,<0.16`.
  [0.24.0](https://pypi.org/pypi/unstructured/0.24.0/json) requires >=3.11,<3.14
  and beautifulsoup4 >=4.14.3, conflicting with docker's >=3.10,<3.11 and K's
  beautifulsoup4 <4.13. Its lxml >=5,<7 and parser dependencies also need
  reconciliation. Change `libs/kotaemon/pyproject.toml` only after selecting an
  official 3.10 backport or separately authorizing a Python support migration;
  the latter additionally affects root/docker manifests, Dockerfile and Native
  interpreter inputs. Do not silently add unstructured PDF/all-docs extras.
  Regress the unstructured PDF reader, NLTK compatibility and runtime bootstrap;
  add bounded URL/private-network/redirect SSRF cases. No solution installed.
- **NLTK: no released fix candidate.** `K -> nltk` requires >=3.10.3,<4;
  llama-index core/legacy and unstructured also introduce it. Core excludes 3.9
  but otherwise accepts >=3.8.1; legacy requires >=3.8.1; current unstructured
  adds no NLTK cap. Official advisory and [current release metadata](https://pypi.org/pypi/nltk/json)
  still end at affected 3.10.3. A future official fix must cover model-artifact
  read/write APIs; existing tokenizer/resource tests do not cover that fix.
  Then update the K manifest and common generated files, run
  `test_nltk_compatibility.py`, `test_runtime_bootstrap_nltk.py` and offline
  container tokenization, plus local path/symlink negative controls. Removing
  NLTK also requires replacing its llama-index/unstructured consumers.
- **Chroma: no released fix candidate for the three rows.** `K -> chromadb`
  is capped <=0.5.16, and `K -> llama-index-vector-stores-chroma 0.1.10 -> chromadb`
  requires >=0.4,<0.6. [Latest 1.5.9](https://pypi.org/pypi/chromadb/json) remains
  affected in all three official records. MARA's local `PersistentClient` use
  differs from the advisories' server/auth/configuration preconditions; it does
  not waive the gate. Require an official release covering all three or a
  separately scoped replacement. A later major update must coordinate the K
  manifest, integration/core and common generated files, then run Chroma
  lifecycle/vectorstore/indexing tests and disposable persisted-collection
  migration tests. Never test migration on real collections.

Published alternatives checked on the same date are AnyIO 4.15.1, Soup Sieve
2.10, pypdf 6.19.0, Transformers 5.18.0 and Unstructured 0.27.10. They are not
selected for a blanket upgrade, solved together, or asserted to have an LTS
support guarantee. Chroma 1.5.9 and NLTK 3.10.3 provide no fixed alternative.

### PCRE2: exact target, file and distribution repair

The three original reports identify **Debian 12.14 / amd64**, source package
`pcre2`, binary package **`libpcre2-8-0 10.42-1`**, analyzed by `dpkg`.
Their package inventories identify the exact installed library
**`/usr/lib/x86_64-linux-gnu/libpcre2-8.so.0.11.2`**. The vulnerability entries'
`PkgPath` is absent; the file association comes from `Packages[].InstalledFiles`,
not an invented scanner path or a Python wheel. All three findings use base
DiffID `sha256:b05a96227958df6091396f6fbd5aa4616df631a65626ac8688c91cfa70d1a7e6`.
Provenance ties that Debian layer to the pinned Python Bookworm image above.

| Original target / job | Original scanned image ID                                                 | Retrieved artifact |
| --------------------- | ------------------------------------------------------------------------- | ------------------ |
| lite / 108948913061   | `sha256:db45e325a50dcfcab3398c0db58d4655beb683bf2b46c660acd00e8911b175f5` | 10973057791        |
| full / 108948913161   | `sha256:0e157b5df749271cade0ab3db539b0870fb4c753a9b0759dc8bb698962439ebf` | 10973575063        |
| ollama / 108948913005 | `sha256:fdcb4a37a68c3d20484237f554f8b6735fb1703a5cc23fb98674df04ebb7b6ea` | 10972914994        |

Each target retains these three rows individually:

| Original CVE                                                                 | Confirmed upstream relationship / condition                              | Original fixed field and Bookworm minimum |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ----------------------------------------- |
| [CVE-2026-86145](https://security-tracker.debian.org/tracker/CVE-2026-86145) | GHSA-3r4p-g7gg-ppmf; DFA workspace bounds                                | 10.42-1+deb12u1                           |
| [CVE-2026-89157](https://security-tracker.debian.org/tracker/CVE-2026-89157) | GHSA-q8g2-wprr-34m9; large pattern on 32-bit platforms                   | 10.42-1+deb12u1                           |
| [CVE-2026-89161](https://security-tracker.debian.org/tracker/CVE-2026-89161) | Upstream PR 937; copied-subject/JIT free; no GHSA alias established here | 10.42-1+deb12u1                           |

Upstream fixes are in 10.48; Debian backports them without renumbering to 10.48.
The 32-bit condition in 89157 is distinct from these amd64 images; preserve the
raw finding and unchanged gate without adding an exception. Other vulnerable
API preconditions were not exercised in the application.

**Batch 2 candidate: `libpcre2-8-0=10.42-1+deb12u2`.** The official
[Bookworm security amd64 package index](https://security.debian.org/debian-security/dists/bookworm-security/main/binary-amd64/Packages.xz)
currently offers that version; its libc6 >=2.34 requirement is met by the
original image's 2.36-9+deb12u14. Package SHA256 is
`d2f7edfcc7689b9e0761c2742cc824ac86a20768bc5e8057818dc6875291fe76`.
The minimum change is **Dockerfile's existing `runtime-base` apt install list**:
add that exact package. Lite/full/ollama inherit the repaired runtime base.
Keep the base digest and Python locks; no broad apt upgrade, regex/wheel update,
manual shared-library replacement or builder-only change is needed to address
this observed final-image file. A newer base digest is an alternative only after
its actual dpkg contents are verified, not a presently identified candidate.
No apt simulation, package installation or new build was performed here.

After that separate batch, verify actual image package version, `dpkg-query -S`
ownership, symlink target and bounded `grep -P` behavior, then the existing
`scripts/smoke_container_runtime.py` and unchanged Trivy/baseline checks for each
new target. Preserve newly produced image IDs and reports; old image/secret
results cannot certify changed bytes. This system-package-only batch does not
change Desktop's Python freeze inputs.

### First implementation batch and stopping boundaries

Order executable batches as **1 AnyIO -> 2 PCRE2 -> 3 Soup Sieve**, keeping their
commits and results separate: AnyIO addresses the container CRITICAL TLS row
with compatible parent bounds; PCRE2 has a distribution ABI-preserving backport;
Soup Sieve has a small compatible parsing update. Then assess the coupled pypdf
reader batch, Transformers/model/UI batch and Unstructured/Python-support batch.
NLTK/Chroma remain explicit upstream-fix blockers, not permission to suppress
findings. No later batch is automatically authorized by this plan.

For **batch 1 only**, the exact proposed files and versions are:

1. Add `anyio==4.14.2` to `[tool.uv].constraint-dependencies` in `pyproject.toml`
   and `docker/pyproject.toml`. Retain current public Python/platform scope,
   SDK/Gradio/MCP versions, CPU torch and build constraints.
2. In a complete task-owned input copy with the validated storage environment,
   use pinned uv 0.11.19 and targeted `lock --upgrade-package anyio==4.14.2` for
   root and docker. Review the resolution before bringing back `uv.lock` and
   `docker/uv.lock`; stop for unrelated version drift or unsatisfied markers.
   Regenerate `constraints.txt` with the existing sync script. These five files
   are the planned dependency change. Do not hand-edit locks or install into
   canonical during candidate evaluation; the existing install contract governs
   any later canonical installation.
3. Run `python scripts/sync_locked_constraints.py --check`,
   `python scripts/check_container_lock_parity.py`, and
   `python scripts/check_supply_chain_policy.py`. Under each controlled Python
   3.10/3.11 candidate environment run `pytest -q` with
   `libs/kotaemon/tests/test_mcp_live_sessions.py`, `test_mcp_async_errors.py`,
   `test_mcp_operation_lifecycle.py`, `test_mcp_worker_ownership.py`,
   `test_mcp_tools.py` (all in that directory), and
   `libs/slide_cli/tests/test_cli_contract.py`; verify both `MARA --help` and
   `MARA-cli --help`. The live-session cases cover owned loopback services,
   cancellation, error propagation and cleanup. Add bounded local TLS-IDNA and
   worker-stderr regressions where those advisory behaviors lack coverage.
4. Run the unchanged `scripts/check_dependency_audit.py` once per profile with
   `(profile, project, python-version)` equal to `(root-py310, ., 3.10)`,
   `(root-py311, ., 3.11)`, `(container-py310, docker, 3.10)` and platform
   `x86_64-unknown-linux-gnu`. Capture complete outputs even when other original
   findings still cause exit 1. Changed package builds, affected Native runtime
   inputs and actual container images then require candidate evidence under the
   existing gates; none of those executions is claimed in this planning round.

Batch 1 succeeds only when the selected AnyIO version is active in all profiles,
both locks and generated constraints agree, relevant regressions pass, the two
original AnyIO Python advisories and corresponding container TLS row disappear
under unchanged rules, and no unexplained new finding or unrelated dependency
change is introduced. Remaining S1 rows/legacy debt still block overall delivery.
Rollback means reverting only that batch's five named dependency files before
publication; it does not restore/migrate user DBs or dispose of historical caches.

The bounded preview here used the verified uv 0.11.19 binary (SHA256
`cd628b46729d01ad110146a647a633a6e5de0e091d73db46afaeee6fcb4ba648`), explicit
cache/temp/project-environment/Python paths, disabled interpreter downloads and
`--no-build`. Read-only frozen trees completed for all three profiles. An initial
interpreter auto-selection was replaced by the explicit task interpreter; all
three tree outputs were byte-identical. Root/docker `lock --dry-run` each exited
**1** because workspace dynamic metadata for `kotaemon`/`mara-app` requires a
build that `--no-build` forbids. The guard was not relaxed. Thus parent-bound and
wheel-metadata checks passed; **full resolution and installation are unverified**.
A future implementation must authorize and isolate that necessary first-party
metadata build, not silently execute package setup code in a planning preview.

The unchanged container baseline has `expires_on: 2026-10-04`; its existing code
rejects dates **after** that date. Even removing these specific findings will
not authorize extending the baseline or claiming a later green gate. Legacy
security disposition remains separate. The current accepted structure/P-UV/
DL-POSIX evidence remains historical; dependency changes invalidate applicability
of old package/Native/image results to the candidate. Input-identical unaffected
component evidence may be cited with its original SHA/date, without repeating
whole-product acceptance or starting U1.

Planning evidence is in
`D:/MARA-s1-01a086ff/s1-plan-20261004/`: `remediation-plan.json` contains all 54
original rows, advisory mappings, complete incoming paths, metadata and proposed
regressions; `source-index.json` indexes official responses, old artifact ZIPs,
frozen trees and both failed previews. Index SHA256:
`79fe75049de200c88d22f400716b65583a299bd36c1c797f728e0f3873bc8715`.
The report is the only repository change. The 135 protected hashes and NUL
remain unchanged; real runtime resources and the eight historical UV incident
directories were not rescanned or modified. Stop after this plan: S1/PCRE2 OPEN,
U1 deferred, historical incidents OPEN, R6-D BLOCKED / not ACCEPTED and
merge/release NO-GO. R5/R6-B/R6-C acceptance remains unchanged.

## Retained limited P-UV / DL-POSIX execution (2026-09-28)

**P-UV forward installation and the controlled DL-POSIX contract pass within
their measured scope. R6-D overall remains BLOCKED and is not ACCEPTED.** The
original UV-cache event, older configuration/cache protection events and required
security gates remain open. The current image secret scan also failed before
completion. R5, limited R6-B and limited R6-C/C1-W/C2-W acceptance is unchanged;
R6-A/U1 is BLOCKED / deferred. Stop at independent R6-D review, with
S1/PCRE2 OPEN and merge/release NO-GO.

This round implements only the two authorized remaining items. It preserves the
structure contracts, developer documentation and prior scope reconciliation;
it does not repeat the whole-repository inventory or start U1, a later phase,
five Gradio exits or either 37-scenario browser batch. Existing required browser
security checks still run and are not U1 evidence.

Baseline: `f8a57979ff9d3f109b5aef5c622ef03b802b70a0`.
Prior verified source/tests/packages: `e7d4f8ad089ea39741c54afb0fb246bc2fd03179`.
Fixed Dev: `adab3f4d8f221e3620494fab0a24ef8e5557d12a`.
Final source/test/package/Quality/native input: `f5d974ce4183eb9e618da49bab5499505029fcb0`.
Evidence root: `D:\PythonProject\MARA-refactor-review-20260910-01a086ff\r6d-puv-dl-closeout`.
Full report/local/remote SHA is bound after ordinary push in `final-delivery.json`;
that report commit is not a new package or CI execution.

| Commit                                     | Separate responsibility                                             |
| ------------------------------------------ | ------------------------------------------------------------------- |
| `46ad6d5fdb235cf4180857d4a12501114f433c3a` | Initial real-open barrier test; observer defect retained below      |
| `0438a9b299212af18dc02e099c889c99d5f2db68` | P-UV spawn-boundary validation and its 51 contract cases            |
| `4863925f8350f9edad24e9e0222feca5aae887d2` | Test-only observer repair; actual deterministic Linux red           |
| `f5d974ce4183eb9e618da49bab5499505029fcb0` | Minimal `.active` lifecycle fix and strict-boundary counterexamples |

### Responsibility and current state

| Item                                 | Owner and treatment                                                                           | Contract / evidence                                                                                      | Current state                                                                           |
| ------------------------------------ | --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Structure/documentation/scope matrix | Prior R6-D owners and compatibility seams retained                                            | Original matrix below; 91 architecture cases in current root collection; full applicable suites          | Prior structural results retained; no new whole-tree completion claim                   |
| P-UV                                 | `scripts/install_owned_wheels.py`; explicit task caller owns root/environment/wheel selection | Original helper characterization, 51 tests, exact current four-wheel install and 49 real console calls   | Forward installation PASS; historical event remains OPEN                                |
| DL-POSIX                             | `artifact_retention._inspect_active`; fixed-name `artifact_secure_fs.active_marker_metadata`  | Actual open/fstat barrier red on Linux 3.10/3.11, final full package suites and safety counterexamples   | Controlled defect fixed; limited contract PASS; historical unique interleaving unproven |
| Package/native delivery              | Existing four Python builds and Desktop Gate2                                                 | Current source rebuilt; four clean installs, Windows/Ubuntu combined directories and authenticated smoke | Measured scope PASS; installer/clean VM/macOS and unfinished features unchanged         |
| Protection/security                  | Existing protection and supply-chain owners                                                   | Forward receipts distinct from historical incidents; actual Quality failures below                       | Overall BLOCKED; no automatic risk acceptance                                           |

### P-UV: the checked configuration is the spawned configuration

The original `install_owned_wheels_uv.py`, disconnected
`owned_installer_preflight.py` and `new-uv-cache-event.json` were read. A controlled
replay intercepted the original helper immediately before `subprocess.run` and
recorded the omitted `UV_CACHE_DIR` / `UV_PROJECT_ENVIRONMENT` and cache argument.
It did not launch uv or write another default-cache entry. This characterization
is separate from the original actual write event (`puv-old-spawn-red.json`).

The new focused helper copies the supplied environment and four wheel hashes
once, constructs the final argv, validates that exact argv/environment/Python/
cache/temp/cwd combination, then makes one subprocess call using those same
objects. No later environment merge or inherited override is applied. It rejects
empty, missing, relative, wrong-root or redirected required paths, ambiguous
casing, inherited UV/PIP/Python overrides, a different interpreter/argument list,
and missing or changed wheels before a child starts. The caller explicitly owns
`D:\MARA-s1-01a086ff`; ownership is not inferred from HOME. This is the local
delivery helper, not a replacement for the canonical `install.sh` contract.

The actual call uses the selected uv binary, `--no-config --offline`, explicit
owned `--cache-dir`, `pip install --python` for the physical owned interpreter,
`--no-index --no-deps --reinstall`, and exactly the four pinned wheels. Cache and
temp directories must already exist under the owned root. There is no
`--no-cache` substitute, dependency sync, automatic retry or canonical change.
The log contains argv, selected path settings and binary hashes, not complete
environment variables, credentials or configuration contents. Actual uv:
`0.11.19`, SHA256
`cd628b46729d01ad110146a647a633a6e5de0e091d73db46afaeee6fcb4ba648`.

Current execution: `puv-current-f5.json` records exit 0; its Python probe confirms
the actual owned prefix and temp location. Four current noneditable wheels were
installed into the prepared task dependency environment. The unchanged original
entry harness then ran **49/49 actual console commands**, from an outside-repo
Unicode cwd using absolute owned `MARA.exe` / `MARA-cli.exe`, with no PYTHONPATH,
editable package or old global-command fallback. App/model/platform help,
listing, validation and fake Codex/Claude install/merge/backup/repeat/error cases
passed. Missing resources return exit 1; doctor exit 0 retains both explicit
missing LLM/embedding warnings and does not claim configured models. No real
tool directory or paid provider was used. Installed bytes matched **985** Git
source/resource files; the owned cache matched **1,010** current wheel members.
The earlier e7-wheel forward run also passed 49 calls and remains separately
labelled; it is not substituted for this current f5 execution. Clean-environment
installation is the separate current Quality job, not this prepared environment.

| Current wheel                               | SHA256                                                             |
| ------------------------------------------- | ------------------------------------------------------------------ |
| `kotaemon-0.0.40-py3-none-any.whl`          | `5657c1aa869afccd5135db8ca1d3186fcbc7b554d4f8235c6ffef644d4b60bc6` |
| `ktem-0.0.40-py3-none-any.whl`              | `0d2fe4f1c3e7669b452c979044495638b414c4d1a35fe63c58b23eecc9055ef0` |
| `mara_app-0.0.40-py3-none-any.whl`          | `0b318fa718287fae4ca4e80def53dee317125e4a61238264431cff33f95ac725` |
| `mara_research_cli-0.0.40-py3-none-any.whl` | `e957d29084e4bf43202f4ce4e6f58ad02704dc4fec1e4a911869a3ed52be3178` |

### DL-POSIX: real publication between open and fstat

The prior incident at run `36396816657`, job `108846199368`, failed in the
original concurrent download case without inode/link/interleaving observations.
It remains historical failure evidence, not a uniquely attributed race.

The new test pauses after the actual native `open(".active")` and before its
production metadata check, while the producer lease is observed held. The
producer then publishes ready/payload and unlinks that same active inode;
the scanner resumes after publication returns.
The first observer accidentally replaced the `os.open` identity used by the
native capability check. It never reached the intended barrier, so run
`36425292325` at `46ad6d5f` is an observer failure, not the product red. The
separate `4863925f` repair observes only retention's `os` reference and preserves
the native capability identities.

Actual red run `36426417557`, attempt 1, then failed the production check on both
Linux Python versions: each job recorded **1 failed, 479 passed, 10 existing
skips**. Python 3.10 job `108942068132` observed inode `10493632`; Python 3.11 job
`108942068068` observed inode `6041414`. In each case mode was `33152`, nlink
changed **1 → 0** on the same inode, the producer lock was held at the open
observation, and after publication the active name was absent, ready nlink was 1
and payload was `owned-publication`. The
actual error was `ArtifactNamespaceError: Download lifecycle marker is unsafe`.
`dl-posix-red.json` binds these observations to the raw CI logs. Both diagnostic
runs retain their actual cancelled overall state (8 success / 6 failure /
6 cancelled jobs), including the completed test failures; neither is relabelled
as final acceptance or assembled with later passing jobs.

The fix opens only `.active` with the existing no-follow flags, tries the
nonblocking lease before final metadata, and inspects the fixed name. A regular
open inode with **nlink 0 and absent `.active`** means its transient lease has
finished; that descriptor is closed once and existing ready inspection proceeds.
The second fstat only resolves unlink between the first fstat and name lookup.
Otherwise regular mode, nlink 1 and matching named inode remain mandatory.
Moving the metadata decision after lease acquisition also prevents a newly
published output being classified stale using the old producer timestamp.

Shared `_open_regular_entry` is unchanged. Ready authorization and its unlink/
hardlink/symlink/replacement rejection remain strict; active hardlinks,
replacement, rename and symlinks are rejected. Tests retain TTL/capacity/transfer
leases, corrupt/oversized/foreign-context receipts, close failures and primary
error precedence. The original same-file concurrent case is unchanged. No
global tolerance, serialization, retry loop, new skip/xfail or scan-budget change
was added. The final two Linux suites pass **492 cases each, with the same 10
existing skips**; the real POSIX cases execute there. Windows retains its secure
FD capability boundary; portable cleanup tests and native smoke are not a claim
that POSIX FD operations ran on Windows.

### Stable current gates, coverage and actual CI

Local stable adjacent/architecture/installer contracts: **162 PASS** (51 P-UV,
91 architecture, 20 portable download/retention). Changed-file hooks and full
hygiene pass. A mistyped initial test path (exit 4, no tests), formatting/type
corrections and the first oversized draft's hygiene failure remain in the ledger.
The production fix was simplified within existing filesystem ownership; no
baseline was changed to admit it. Local source tests include protected working
overlays; the immutable CI and packages use committed Git inputs.
While coverage was running, one log-API request returned 404 and a read-only
GitHub browser lookup could not reach the browser provider. Those observation
limits remain in `running-coverage-observation-limit.json`; they were not used
to infer a test result or trigger another run. Final logs were collected after
the same job completed.

[Quality 36428131096](https://github.com/262412/MARA/actions/runs/36428131096),
attempt 1, source `f5d974ce4183eb9e618da49bab5499505029fcb0`: **failure**,
**12 success / 8 failure** across
20 actual jobs. This is the sole final-candidate dispatch.

| Actual job                                                 | Job ID                                                                                   | Result  |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ------- |
| kotaemon Python 3.11                                       | [108948912609](https://github.com/262412/MARA/actions/runs/36428131096/job/108948912609) | success |
| Repository and image secret scans / Built image            | [108948912840](https://github.com/262412/MARA/actions/runs/36428131096/job/108948912840) | failure |
| slide_cli                                                  | [108948912887](https://github.com/262412/MARA/actions/runs/36428131096/job/108948912887) | success |
| ktem isolated runtime                                      | [108948912902](https://github.com/262412/MARA/actions/runs/36428131096/job/108948912902) | success |
| Static, hygiene, and baseline ratchet                      | [108948912924](https://github.com/262412/MARA/actions/runs/36428131096/job/108948912924) | success |
| Python distribution supply chain                           | [108948912958](https://github.com/262412/MARA/actions/runs/36428131096/job/108948912958) | success |
| Container ollama supply chain                              | [108948913005](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913005) | failure |
| Repository and image secret scans / Repository and history | [108948913045](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913045) | success |
| Benchmark and root contracts                               | [108948913054](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913054) | success |
| Coverage floors and production diff                        | [108948913057](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913057) | success |
| Container lite supply chain                                | [108948913061](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913061) | failure |
| kotaemon Python 3.10                                       | [108948913138](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913138) | success |
| Four clean wheel installations                             | [108948913148](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913148) | success |
| Container full supply chain                                | [108948913161](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913161) | failure |
| Dependency audit root-py310                                | [108948913196](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913196) | failure |
| Unified pytest collection                                  | [108948913198](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913198) | success |
| Dependency audit root-py311                                | [108948913244](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913244) | failure |
| Dependency audit container-py310                           | [108948913261](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913261) | failure |
| Frontend and browser security                              | [108948913346](https://github.com/262412/MARA/actions/runs/36428131096/job/108948913346) | success |
| Required quality gates                                     | [108971920599](https://github.com/262412/MARA/actions/runs/36428131096/job/108971920599) | failure |

Current suites: kotaemon 3.10/3.11 **492 PASS + 10 existing skips each**;
ktem **3,989 PASS**; benchmark/root **1,806 PASS**; slide CLI **163 PASS**;
frontend **40 Node + 8 browser-security PASS**. Unified collection contains
**6,626 nodes**, with the unchanged 1,260 floor. Four wheels and four sdists,
provenance/SBOM payloads and four clean wheel installations pass. The eight
downloaded distributions and all 141 platform assets match current committed
inputs. These counts describe their actual suites, not all product capabilities.

| Original package scope | Covered/statements | Coverage | Unchanged floor | Result |
| ---------------------- | ------------------ | -------- | --------------- | ------ |
| benchmark              | 17146/19005        | 90.218%  | 90%             | PASS   |
| slide_cli              | 2358/2878          | 81.932%  | 70%             | PASS   |
| kotaemon               | 8013/11098         | 72.202%  | 60%             | PASS   |
| ktem                   | 43808/51906        | 84.399%  | 50%             | PASS   |

| Production diff base                   | Covered/changed executable lines | Coverage | Result |
| -------------------------------------- | -------------------------------- | -------- | ------ |
| fixed-dev (`adab3f4d`)                 | 2642/2735                        | 96.600%  | PASS   |
| limited-round-increment (`f8a57979`)   | 32/33                            | 96.970%  | PASS   |
| r6d-increment (`bef108c6`)             | 32/33                            | 96.970%  | PASS   |
| accepted-source-increment (`5474ec2c`) | 32/33                            | 96.970%  | PASS   |

Diff threshold remains 90%. P-UV's `scripts` path stays outside the original
production diff scope; its separate 51 cases and actual install evidence are
required. Coverage does not establish architecture, authorization or historical
protection integrity. `final-coverage-summary.json` retains denominators,
missing lines, actual CI job and coverage artifact hash.

The three dependency jobs each report **14 findings relative to the frozen
baseline**; each container audit reports **4**. Their identities are unchanged
relative to prior e7 run `36398097945`: **zero added and zero removed** in this
round. Separately, image secret job `108948912840` failed with
`semaphore acquire: context deadline exceeded` while analyzing an installed
transformers `.pyc` in its image layer. Its scan is **incomplete**, not a new
detected-secret finding or a PASS. Repository/history secret scan passed.
The required aggregate remains failed. No same-SHA retry, timeout expansion,
lock/baseline/alias/allowlist/required-job change or security upgrade was made.

### Current native rebuild and platform limits

Changing packaged kotaemon code required a new native build.
[Desktop Gate2 36428120919](https://github.com/262412/MARA/actions/runs/36428120919),
attempt 1, uses the same final f5 source and is **3/3 SUCCESS**: Ubuntu 22.04
job `108947065218`, Windows 2022 job `108947065396`, and the same Linux package
on Ubuntu 24.04 job `108950506129`. Both builders pass **118 Electron + 41
renderer + 5 packaging + 152 Sidecar tests**, current frozen Sidecar/Electron
combined-directory construction, outside-repo authenticated business smoke and
owned-process shutdown. No old native SHA is reported as this execution.

The downloaded Linux archive SHA256 is
`1f730ef8e5bf7968a87bb2e6d30e07101e9f2922dd9ac36397693a394d618687`;
Windows archive SHA256 is
`4ee352fc152ae547b25fa7abacb63b556db6ff1c0a549cd4319abbac0307f2cb`.
Sidecar binary hashes are respectively
`c7833f3505899d54d6b77f83014b0edd3f7abf25d3d118f8105f157838e9f3c8` and
`a4f0f3b5ade81a9223dee29cfc6f5e9b7e50a2acd81f0fec789b5752863deb6f`.
All **2,096 Linux files/resolved links** (including 32 links) and **2,663 Windows
files** match CI inventories; runtime/config/test exclusions, safe package links
and tokenizer resources pass. Defender reports no detections. Identified owned
processes remaining: zero. Unclassified access-denied host processes remain a
limit: **151 Linux / 14 Windows**, not whole-host process-cleanliness proof.

Installers, clean VM and macOS remain NOT VERIFIED. Unimplemented Desktop
features and optional Office/media/model/backend conditions are unchanged.
The historical Windows 99 root failures, four kotaemon capability failures,
nine additional Windows nodes and full Windows mypy limitations remain recorded
separately; current Linux/native success does not mark them all passed.

### Forward protection, historical disposition and review boundary

This round's explicit forward receipts retain **135 user changes**, NUL,
canonical environment metadata (98,853 entries), actual MARA cache metadata
(610), office cache (0), two DB metadata records and three private config hashes.
No protected overlay enters a committed file or wheel. The eight already known
UV incident directories, including their URL-parent lock/revision files, retain
the same metadata and **1,022 file hashes** as this round's starting receipt.
Only those known incident paths were checked; no new historical search was made.

The **original UV incident remains OPEN**: the old task installer is the evidenced
writer, but no pre-incident default-cache byte inventory exists. The new isolated
install and current unchanged receipt do not prove original absence/integrity or
authorize removal. The four index parents and four archive targets remain in
place. Separately, older configuration writer UNKNOWN, original bytes UNVERIFIED
and the MARA cache 614 → 610 event OPEN remain unresolved. No restore, mtime
adjustment, cache clean/prune, canonical sync or cleanup of history was performed.
There is no blanket historical protection PASS.

`report-input-equivalence.json` checks the entire Git tree excluding this report
and confirms the report is absent from all eight distribution payloads. Actual
source/package/native provenance stays at f5. Final delivery additionally checks
the final report commit's secret scan, exact protected hashes and local/remote
HEAD; those post-commit receipts are in `final-delivery.json`. Ordinary named-path
commits/push only; no new branch/worktree, force push, merge, deployment or release.

Remaining actions are bounded: independent review of the two fixes; owner
disposition of the eight UV paths and older protection events; existing S1/PCRE2
dependency/container owners plus the incomplete image-scan job; and U1's existing
deferred lane and recorded platform/product limits. No independent item is
silently converted to acceptance, and no further phase or U1 campaign starts.

## Retained R6-D implementation and delivery review at f8a57979 (2026-09-28)

The user independently accepted **R6-C, C1-W and C2-W within the reviewed
implementation, artifacts and actual platform scope**. R5 and limited R6-B remain
ACCEPTED. R6-A/U1 remains **BLOCKED / deferred** and did not gate this independent
work. Historical red/BLOCKED/NOT RUN evidence below is unchanged.

R6-D now has executable structure/compatibility contracts, corrected developer
documentation and current installed/native delivery evidence. **Independent
structure and native subitems pass; local installed behavior is observed but its
protection closeout is HOLD; full-repository closeout remains BLOCKED** by the new
UV-cache boundary event, the newly observed POSIX download concurrency failure
and the separate required security gates. This is an independent review handoff, not
automatic ACCEPTED, all-feature acceptance or release approval.

Baseline: `bef108c668fa84f44b02e5f10fc105462a205713`; reviewed prior input:
`5474ec2c7f49f72cc5b66ae645522fb16e6ef554`; prior Windows/native actual tree:
`f659007ee9693fb9f8603850ccfbbd00f56ff5cc`; fixed original Dev:
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`.
Current source/test/four-package/Quality input: `e7d4f8ad089ea39741c54afb0fb246bc2fd03179`.
Current native execution input: `20c6d05c99c6d1da1b51274e6f2f20efc180d46c`.

Evidence root: `D:\PythonProject\MARA-refactor-review-20260910-01a086ff\r6d-architecture-delivery`.
`verified-inputs.json`, `execution.jsonl`, `native-input-applicability.json`,
artifact receipts and the final report-only `final-delivery.json` retain full
hashes, commands, logs and local/remote provenance. Report-only reuse must match
the entire tree excluding this report and include a final secret scan.

| Actual commit                            | Purpose                                                            |
| ---------------------------------------- | ------------------------------------------------------------------ |
| a23950af81d99febae04298f9c3604fe6c776bad | docs: start R6-D after limited R6-C acceptance                     |
| ebde7a33c807bdefe6275b785a775f5ed8fcb6a3 | test: enforce accepted extraction and compatibility boundaries     |
| 20c6d05c99c6d1da1b51274e6f2f20efc180d46c | docs: align setup and delivery boundaries with verified contracts  |
| c20f5c5e6ef5b505efdc217a0e7a079926428348 | test: align source-install documentation contract with owned setup |
| 2db6ea8e3212d52ab3fd134e05f8f55cbae6ea9e | docs: specify bundle list merge and scalar preservation            |
| 2024bbaf59acf2281675baec1b920e3439bac55e | style: normalize current report section separator                  |
| e7d4f8ad089ea39741c54afb0fb246bc2fd03179 | test: retain legal path operations and verify lazy MCP imports     |

The following report-only commit's full report/local/remote SHA is recorded by
`final-delivery.json` after normal push and in the handoff; it is not mislabelled
as a new source, package, native or CI execution.

### Original plan → owner → treatment → contract → evidence → state

The R0 map, R1 location plan, R6 remaining matrix,
`r6d-preparation-shutdown.json` and `entry-and-package-map.json` are the inputs.
The earlier 15-module review is an owner-map input, not whole-repository proof.

| Original plan domain          | Responsible owner                                                                        | Treatment                                                              | Contract / actual evidence                                                                                       | State and limit                                                                                                                          |
| ----------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| R0/R1 shared rules            | `ktem_contracts/file_selection.py`; Runtime/ChatPage adapters                            | Already refactored; compatibility retained                             | Existing normalization/merge and cold-import tests; new reverse-import negative controls                         | Structural contracts verified; old normalize/merge semantics retained                                                                    |
| R2 runtime/import composition | `ktem.docqa` runtime facade, `_runtime_*`, service factories; neutral contracts package  | Reasonable orchestration retained                                      | Existing package/cold-import suites and unchanged public surfaces; no new DI/repository layer                    | Verified within suite scope; eager `kotaemon.agents` facade intentionally retained                                                       |
| R3 Web event/presentation     | `pages/chat` adapters, `file_browser_rendering`, JS/DOM consumers                        | Accepted extraction retained; rendering guard added                    | AST reverse-import and I/O counterexamples; existing event/security tests                                        | Structure verified; U1 BLOCKED/deferred, natural full browser NOT RUN here                                                               |
| R4 planning/binding           | `finance_plan_policy`, `evidence_binding_policy`; original planner/binder                | Already refactored; legal helper/lazy seams retained                   | New dependency directions plus existing strategy, binding, copy/identity and patch contracts                     | Structural and existing behavior suites; no prompt/metric/schema change                                                                  |
| R5 storage/index/cache        | Source locks, graph cache, session/Notebook services, artifact registry, writer/ZIP      | Accepted owners retained                                               | Existing Linux package contracts; previous R5 failures and paired 37 matrices retained                           | Prior acceptance unchanged; new adjacent download finding OPEN below                                                                     |
| R6-A inspection/CLI           | `docqa_inspection`, runtime factory/profile, import capabilities, Click adapters         | Read-only owner and compatibility retained                             | Inert/forbidden-import guards, existing actor/identity/record/patch tests, installed aliases                     | Inspection structure verified; whole R6-A/U1 remains BLOCKED                                                                             |
| R6-B launch/lifecycle         | `sidecar-launch.ts`, `smoke-environment`, manager/main, application/IPC/task/SSE owners  | Accepted split retained; launch guard added                            | Semantic TS negative controls; 118 Electron, 41 renderer, 152 Sidecar, 5 packaging tests on both native builders | R6-B ACCEPTED limited scope; new native input/result below                                                                               |
| R6-C MCP/agent                | `mcp`, `mcp_operation`, `mcp_session`; BaseTool/agent config consumers                   | Accepted operation/session split; public identities retained           | SDK cold-process guard, actual facade patch consumer, original sync/async/stdio/SSE/cancellation tests           | R6-C/C1-W ACCEPTED limited reviewed scope; no live user server/provider used                                                             |
| R6-C deck/artifacts           | `deck`, `deck_export`; artifact registry and R5 Notebook services                        | Accepted content/export split; old type and patch paths retained       | Added export/type identity consumer; existing real deck/stale conversion/resource tests                          | R6-C/C2-W ACCEPTED limited reviewed scope; Office/media capabilities remain conditional                                                  |
| Benchmark/scoring             | Existing CLI, runner, scoring, dataset adapters and frozen fixtures                      | Reasonable modules retained                                            | Full benchmark/root suite; prior micro-manifest actual command/score/report chain retained                       | No training, new benchmark experiment or performance claim                                                                               |
| App/model/platform support    | `kotaemon.cli`, model routing, platform registry/specs/assets                            | Existing names/aliases/config merge semantics retained; docs corrected | 49 installed console calls; owned Codex/Claude targets, dry run, backup, repeat, missing-resource counterexample | Functional calls verified; local installation protection HOLD for new default UV-cache writes; real `.codex`/`.claude` targets untouched |
| Python delivery/resources     | Four pyprojects/manifests, CLI scripts, JS/CSS/PDF.js/platform resources                 | Package names and resources retained                                   | Four wheel+sdist builds, four clean installs; 985 Git-byte comparisons including 141 platform assets             | Current package input verified; not all provider/platform capabilities                                                                   |
| Desktop product/native        | Electron/PyInstaller combined directories and existing feature matrix                    | Implementation retained; support limits clarified                      | Current Windows/Ubuntu builds and outside-repo authenticated smoke; exact native input equivalence               | Combined directories verified; installers/clean VM/macOS and unfinished Desktop features NOT VERIFIED/NOT IMPLEMENTED                    |
| Developer docs/gates          | Contributing, hygiene, README, mkdocs, platform and Desktop guides; scripts/workflows    | This-round small corrections and executable contracts                  | 96 local Markdown targets; existing static/hygiene/collection/coverage/secret/Quality gates                      | No lock/baseline/alias/runner/required-job/threshold changes; security NO-GO                                                             |
| Auxiliary/generated/vendor    | IDE files, prior artifacts, generated schema/locks, fixture data, vendor assets/licenses | Reasonable/history/compatibility retention                             | Incremental Git path/blob reconciliation and packaging checks only                                               | Retained by role, not certified as executed features or deleted as clutter                                                               |

### Incremental tracked-tree coverage

One reconciliation reused the original disjoint classifier and Git blob
identities, without rescanning real runtime data or rebuilding a dependency
inventory. Historical Dev had 2,436 tracked files; this candidate has **2,729**:
2,292 unchanged, 144 modified and 293 added relative to fixed Dev; no deleted or
renamed paths. The path set at `20c6d05c` and `e7d4f8ad` is identical.
These are file-role denominators, not a feature, architecture or completion
percentage. The 135 protected working overlays and NUL are outside package
inputs and have separate receipts.

| Current tracked area | Files | Treatment                              | Evidence / limit                                                                  |
| -------------------- | ----- | -------------------------------------- | --------------------------------------------------------------------------------- |
| .codex               | 49    | Compatibility retained                 | Shipped skill names and protected user overlays; test installed copies only       |
| .githooks            | 1     | Reasonable retained                    | Canonical/worktree ownership hook; existing environment contracts                 |
| .github              | 16    | Reasonable retained                    | Existing Quality/native workflows executed, policies unchanged                    |
| .idea                | 10    | History retained                       | No runtime/functional validation claim                                            |
| .playwright-cli      | 10    | History retained                       | No U1/Login/browser campaign                                                      |
| .superpowers         | 21    | History retained                       | Existing plan/evidence; no deletion                                               |
| .tmp_publish_check   | 6     | History retained                       | No new publication or deployment                                                  |
| .vscode              | 1     | Reasonable retained                    | Developer configuration preserved                                                 |
| apps/desktop         | 163   | Accepted + this-round guard            | Current native and source tests; incomplete product/installer boundaries retained |
| benchmark            | 461   | Reasonable retained                    | Full contracts; external datasets/GPU/providers conditional                       |
| docker               | 2     | Reasonable retained / security blocked | Actual three-target build/smoke/audit; S1/PCRE2 open                              |
| docs                 | 108   | This-round small corrections           | Current guidance/report changed; history preserved                                |
| libs/kotaemon        | 415   | Accepted + compatibility tests         | MCP/cold import/platform/resources; adjacent download finding open                |
| libs/ktem            | 1141  | Accepted owners retained / U1 deferred | Current full Linux contracts; protected overlays excluded from packages           |
| libs/slide_cli       | 59    | Accepted + compatibility/doc tests     | Current installed aliases, inspection and deck contracts                          |
| local_backends       | 3     | Reasonable retained / optional         | No new backend deployment or full local-provider acceptance                       |
| root                 | 38    | This-round docs / retained packaging   | README/contributing corrections; four distributions unchanged by name             |
| scripts              | 123   | Reasonable retained                    | Isolation/install/coverage/delivery gates; no scheduler or policy changes         |
| templates            | 10    | Compatibility retained                 | Existing templates/resources; no user configuration initialization                |
| tests                | 92    | This-round semantic guards             | Existing root collection; not a new architecture framework                        |

Disjoint current roles: asset 19, auxiliary-history 31, config-or-delivery 105, docs-or-platform 311, fixture-or-resource 91, generated-artifact 16, generated-lock 5, generated-source 1, source 1231, test 913, vendor 6.
`tracked-tree-reconciliation.json` preserves every path, role, area and blob
delta. The current matrix does not turn unchanged modules, optional adapters or
historical generated artifacts into verified product capabilities.

### Actual structural changes, compatibility and negative controls

This round changes five test files and eleven documentation/navigation/report
files. **No production module, package name, signature, CLI option, schema,
persisted ID, Gradio component/DOM or skill name changed.** No blanket rename or
compatibility deletion was justified by consumer evidence.

- Root `tests/test_refactor_architecture_contracts.py` covers nine Python
  owners: neutral file selection, finance planning, evidence binding, rendering,
  inspection, MCP operation/session/facade and deck export. AST guards resolve
  absolute, relative and literal dynamic imports and distinguish call-time
  imports from eager defaults/decorators/classes. Each owner has rejecting
  in-memory counterexamples; legal helpers/lazy integrations remain accepted.
- Rendering checks reject explicit filesystem acquisition and permit pure
  label operations such as `os.path.splitext` and `Path(...).suffix`. This is a
  bounded semantic guard, not whole-program alias/data-flow or authorization
  proof. Computed classpaths remain real consumer-test responsibilities.
- `sidecar-launch-boundary.test.ts` uses the already locked Rolldown/Oxc parser,
  not text grep. It rejects manager/Electron/process ownership through imports,
  exports, require, import-equals and dynamic imports, and accepts environment
  composition/comments/strings. Its eight tests run in existing Electron/native
  collection; there is no new architecture framework, dependency or workflow.
- MCP public type/dynamic facade identity, actual patched session consumption,
  fresh-process SDK-lazy import, deck export/stdlib patch identity and original
  `ShapeSnapshot` ownership remain executable package contracts. Behavioral
  normalization, planning/binding, SQL/identity, cancellation and conversion
  authorities stay in their existing tests rather than being copied here.

Local evidence: initial direct contracts 139 PASS; final affected Python
contracts 111 PASS; Electron 118/118; changed-file hooks PASS. These are distinct
runs/inputs, not stitched into a fictional full batch. Full final Linux/Node and
collection evidence is the current Quality table below.
Unified collection includes all 91 root architecture cases, 20 MCP contract
cases, nine deck/export contract cases and four installation-document cases in
their existing owners; the full repository collection has 6,562 nodes. These
file totals include existing tests, not 6,562 newly added tests.

Retained corrections: the first TS fixture compile required the installed TS7
type-only ESM resolution mode; the original source-install README assertion
still required obsolete direct `uv sync` text and was aligned with the existing
owned `install.sh` contract. The report separator's Prettier failure was fixed
without changing its retained tail. All earlier logs remain; no skip, xfail,
golden refresh or baseline update was used.

### Documentation and installed entry/resource evidence

`CONTRIBUTING.md`, development contributing and README now link to the actual
MARA setup/storage contracts. They remove old editable/direct-sync/source-env
recipes and obsolete cache-bump guidance. The hygiene contract names current
owners and the real eager agents facade, and replaces the obsolete collection
warning with current isolated collection guidance. The architecture guide is
linked from README, development index and mkdocs. Platform docs describe
dictionary/list merge and existing scalar preservation; Desktop docs distinguish
combined directories from installers, clean VMs and unfinished features.
All original gate thresholds and storage protections remain. The link audit
checked 96 local Markdown targets, not every anchor or external URL.

Final Quality built all four wheels and sdists and performed four clean wheel
installations. Downloaded distribution hashes, declared provenance, SPDX and
SBOMs match the final input. Independent payload comparison matched **985**
committed files, including all **141 platform assets**, the neutral contracts
package, JS/CSS resources and both exact console entrypoints. This excludes
protected local overlays; provenance checks are not signature verification.

The four current wheels were installed noneditable into the task-owned prepared
dependency environment, with no dependency resolution. The installer omitted
UV cache isolation: functional results below do not close that protection event.
Outside-repository
Unicode cwd and no PYTHONPATH/editable/global console fallback: **49 actual
console calls passed**. Both MARA aliases expose actual app/model/platform help
and subcommands; model providers used an empty fake config and no paid call.
Codex and Claude Code full installs used only explicit owned targets. Dry-run
purity, primary/sentinel preservation, config merge, original backup, repeated
config stability, status/validation and missing-resource exit 1 were exercised.
The resulting target counts were 102 and 190 files, including owned backups.
Neither the real `.codex` nor `.claude` was an installation target. Console
runtime paths were contained in the owned root; this does not cover the
installer's default UV-cache use recorded below.

The first installation helper found no pip in the owned environment and made no
installation; existing uv installed the four wheels without sync. The first
entry harness incorrectly expected doctor exit 1 when optional models were
absent. Existing `test_docqa_runtime.py` explicitly expects ok=True, no issues
and two warnings in that state. Corrected harness `installed_entries_v2.py`
preserves both warnings and path containment; the original failure remains in
`installed-final`. This is inspection before model setup, not model readiness.
`installed-delivery-details.json` binds both harness hashes and all 49 commands.

### New protection event: installer used the default UV cache

The task's `install_owned_wheels_uv.py` correctly fixed the Python destination
but **omitted `UV_CACHE_DIR`**. At 08:42:23 UTC uv prepared the four wheels using
`C:\Users\22826\AppData\Local\uv\cache`, outside task-owned resources.
This is a new event attributable to this task, not the old MARA cache 614→610
event. The mistake was identified during final boundary review after all local
install/console commands had exited; affected local execution was stopped and
was not repeated to replace the evidence.

The bounded read-only check found four `wheels-v6/url` index directories and
their four `archive-v0` targets. Index pointer bytes identify those archives;
all **1,010 wheel members** match the exact four final wheel payloads. Invocation,
preparation log and these content/pointer links support attribution; overlapping
timestamps merely narrowed the search. Exact paths/hashes are retained in
`new-uv-cache-event.json`. There was no pre-run snapshot of this UV cache, so
original absence/content integrity outside the observed entries is not proved.
No entry was removed, restored or retimestamped, and there was no broad old-cache
investigation. Local installed behavior remains measured, but installation and
protection acceptance are **HOLD / OPEN**.

`owned_installer_preflight.py` now provides an explicit owned cache in both the
future command and environment, rejects wrong/empty cache and wrong prefix
before access (three pure negative controls), and disables Python downloads.
It was only preflight-tested: no new installation was executed after discovery.
Independent CI ran on disposable runners and continues to stand on its own.
Disposition of the eight identified cache directories remains with the owner;
no automatic cleanup or retrospective protection PASS is claimed.

### New adjacent failure: bounded impact and next proposition

Quality `36396816657`, attempt 1, source `2024bbaf`, Linux Python 3.10.21 job
`108846199368`, failed exactly
`libs/kotaemon/tests/test_download_posix_transfers.py::test_same_file_concurrent_generations_and_transfers_are_independent`.
The failure is `ArtifactNamespaceError: Download lifecycle marker is unsafe`
during allocate → scan → inspect active → open `.active` → fstat safety check.
This is a newly observed concrete node, not an old Windows capability failure.
It is **OPEN** even if the later full candidate passes the same unchanged node.

The bounded production scope is `artifact_retention.py`, `artifact_downloads.py`
and `artifact_transfers.py`, with the single existing POSIX test file. These four
files are byte-identical to the round baseline. The log does not record st_mode,
st_nlink or the actual interleaving, so it does not prove a unique cause. The next
minimal test is a deterministic barrier between opening `.active` and fstat
while another owned producer publishes/unlinks it. Determine whether a legal
unlinked inode is rejected, retaining nonregular/hardlink/substitution rejection
controls before proposing any minimal fix. No production safety check was
relaxed and no R5 lifecycle redesign or repeated selection of green runs occurs
in this round. Independent structure/install/native work remains deliverable.

### Current CI, coverage and retained failed runs

[Quality 36398097945](https://github.com/262412/MARA/actions/runs/36398097945),
attempt 1, exact input `e7d4f8ad089ea39741c54afb0fb246bc2fd03179`:
**failure**, {'success': 13, 'failure': 7}. Actual jobs (not a preset count):

| Job and ID                                                                  | Conclusion | Actual evidence                                                         |
| --------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------- |
| Unified pytest collection (`108850209562`)                                  | success    | 6562 tests collected in 46.08s                                          |
| ktem isolated runtime (`108850209672`)                                      | success    | 3989 passed, 140 warnings in 818.98s (0:13:38)                          |
| Static, hygiene, and baseline ratchet (`108850209675`)                      | success    | Actual job log retained                                                 |
| Four clean wheel installations (`108850209689`)                             | success    | Actual job log retained                                                 |
| kotaemon Python 3.10 (`108850209750`)                                       | success    | 479 passed, 10 skipped, 93 warnings in 231.69s (0:03:51)                |
| slide_cli (`108850209771`)                                                  | success    | Quiet pytest progress: 163 passed, 0 skipped, 0 failed/error symbols    |
| Container lite supply chain (`108850209785`)                                | failure    | 4 emitted findings relative to frozen baseline                          |
| Dependency audit root-py311 (`108850209790`)                                | failure    | 14 emitted findings relative to frozen baseline                         |
| Coverage floors and production diff (`108850209791`)                        | success    | TOTAL 2878 520 81.93%; TOTAL 11074 3087 72.12%; TOTAL 51906 8098 84.40% |
| Container full supply chain (`108850209797`)                                | failure    | 4 emitted findings relative to frozen baseline                          |
| kotaemon Python 3.11 (`108850209798`)                                       | success    | 479 passed, 10 skipped, 93 warnings in 234.71s (0:03:54)                |
| Frontend and browser security (`108850209805`)                              | success    | # pass 40; # fail 0; 8 passed (34.1s)                                   |
| Dependency audit root-py310 (`108850209857`)                                | failure    | 14 emitted findings relative to frozen baseline                         |
| Benchmark and root contracts (`108850209884`)                               | success    | 1755 passed, 8 warnings in 586.86s (0:09:46)                            |
| Dependency audit container-py310 (`108850209909`)                           | failure    | 14 emitted findings relative to frozen baseline                         |
| Repository and image secret scans / Built image (`108850209911`)            | success    | Actual job log retained                                                 |
| Container ollama supply chain (`108850209956`)                              | failure    | 4 emitted findings relative to frozen baseline                          |
| Repository and image secret scans / Repository and history (`108850209997`) | success    | Actual job log retained                                                 |
| Python distribution supply chain (`108850210032`)                           | success    | Actual job log retained                                                 |
| Required quality gates (`108861092728`)                                     | failure    | Actual job log retained                                                 |

| Coverage scope | Covered / executable | Percent   | Original floor / result |
| -------------- | -------------------- | --------- | ----------------------- |
| benchmark      | 17146/19005          | 90.21836% | 90% / PASS              |
| slide_cli      | 2358/2878            | 81.93190% | 70% / PASS              |
| kotaemon       | 7987/11074           | 72.12389% | 60% / PASS              |
| ktem           | 43808/51906          | 84.39872% | 50% / PASS              |

| Production diff base                 | Covered / changed executable | Percent                     | Gate exit |
| ------------------------------------ | ---------------------------- | --------------------------- | --------- |
| fixed-dev `adab3f4d`                 | 2610/2702                    | 96.59511%                   | 0         |
| r6d-increment `bef108c6`             | 0/0                          | N/A (no production changes) | 0         |
| accepted-source-increment `5474ec2c` | 0/0                          | N/A (no production changes) | 0         |

No coverage omit, source scope or floor changed. The round's 0/0 production diff
is N/A, not 100% architectural coverage. AST guard reach and functional evidence
are separate from line coverage.

| Security job                     | Relative to frozen baseline | New since reviewed 5474 input | No longer emitted since 5474 |
| -------------------------------- | --------------------------- | ----------------------------- | ---------------------------- |
| Container lite supply chain      | 4                           | 0                             | 0                            |
| Dependency audit root-py311      | 14                          | 0                             | 0                            |
| Container full supply chain      | 4                           | 0                             | 0                            |
| Dependency audit root-py310      | 14                          | 0                             | 0                            |
| Dependency audit container-py310 | 14                          | 0                             | 0                            |
| Container ollama supply chain    | 4                           | 0                             | 0                            |

The comparison uses actual emitted identities in `final-security-comparison.json`.
Supply-chain findings are independently unresolved; no baseline/alias or lock
change hides them. Required aggregate remains actual, not waived.

Retired runs are not combined with this final run: `36396016249` at `20c6d05c`
ended cancelled (6 failure, 6 cancelled, 8 success), including the obsolete
README assertion and report formatting failures; `36396816657` at `2024bbaf`
ended cancelled (5 failure, 6 cancelled, 9 success), including the download
failure. Existing workflow concurrency cancelled unfinished work when corrected
new inputs were dispatched. Each run/attempt/job log and transport-fetch error
is retained. No unchanged-SHA CI was re-dispatched.

### Current native execution and exact reuse limits

[Desktop Gate 2 36396020904](https://github.com/262412/MARA/actions/runs/36396020904),
attempt 1, actual tree `20c6d05c99c6d1da1b51274e6f2f20efc180d46c`: **3/3 success**.
Windows 2022 and Ubuntu 22.04 each ran npm verify (118 Electron, 41 renderer,
152 Sidecar unittest and 5 packaging cases), built the frozen Sidecar/Electron
combination and ran existing authenticated outside-repository business/exit
smoke. Ubuntu 24.04 ran the Ubuntu 22 package. Neither job count nor unit cases
claim installer/clean-VM acceptance or substitute for U1/browser batches.

All Desktop runtime/tests/build/workflow inputs and Python runtime payloads are
identical between this native tree and the final candidate. The five subsequent
changed paths are unrelated Python tests, platform prose and report formatting.
`native-input-applicability.json` enumerates them and verifies the relevant full
scopes; embedded revision and native execution remain **20c6d05c**, not e7d4f8ad.
Prior f659 native 3/3 and Windows C1-W/C2-W receipts remain historical accepted
evidence. Added Python guards do not pretend to be new Windows 93-case runs.

Downloaded native package bytes match CI inventories: Windows 2,663 files;
Linux 2,096 files/resolved links including 32 links. Exact binaries/app.asar and
archives have SHA256 receipts; prohibited runtime/config/test names are absent,
bundled tokenizer resources present, package links remain inside their roots.
Defender reports no detections. Identified owned processes remaining: zero;
inaccessible unclassified host processes remain an explicit limit (Windows 13,
Linux 141). Two bounded Linux archive-transfer interruptions and their partial
files were retained; a range transfer completed the bytes and whole-archive
SHA256 verified. This was artifact transport, not a validation rerun.

Windows 99 historical root failures, four kotaemon capability failures, the nine
additional Windows nodes recorded last round, and full Windows mypy limitations
remain separately recorded. They were not universally rerun or converted to PASS
by Linux CI or native smoke. Installer/clean VM/macOS, full Desktop Notes/Studio/
Graph/export/preview, native picker/IME/secure storage and conditional external
model/media/backend capabilities remain bounded unverified/not-implemented work.

### Protection, remaining owners and independent review stop

Forward receipts after freeze and actual installed commands preserve all 135
user files byte-for-byte, NUL, canonical environment metadata (98,853 entries),
real cache metadata (610), office-cache baseline (0), real DB metadata and the
three configs against this round's private byte hashes. No config contents or
credentials are printed. Final delivery repeats the forward check and verifies
only explicitly named task files were committed; no user overlay enters a wheel.
These receipt domains did not include the default UV cache. Their unchanged
comparisons do not override the new confirmed UV-cache writes described above.

Historical config writer **UNKNOWN**, historical original bytes **UNVERIFIED**
and cache event **OPEN** remain separate. Post-incident snapshots do not prove
historical integrity. No restoration, mtime change, cache cleanup, canonical sync,
new branch/worktree, force push, merge, deployment or publication occurred.
Dependency locks, aliases, baselines, runner policies, required jobs, scanning
scope and coverage thresholds are unchanged. No global all-protection PASS or
automatic risk acceptance is claimed.

Remaining work is finite by owner: the four-file POSIX download proposition
above; the installer helper/default-UV-cache event and its eight recorded paths;
U1's existing chat event/selector/browser fixture lane (deferred, no new
Login/exit/double-37 campaign); the existing Desktop feature/install/platform
matrix; and S1/PCRE2's existing dependency/container security owners. Missing
external-provider/GPU/Office conditions stay optional/conditional rather than
blocking unrelated structural review. Historical protection disposition requires
independent evidence/owner decision and was not reopened without a new lead.

The deferred U1 evidence scope is the existing `tests/browser/conversation_tails.cjs`,
`tests/browser/fixture_exit_probes.cjs`, `tests/browser/browser_fixture_exit.py`
and `libs/ktem/ktem_tests/file_browser_app_fixture.py`; these are bounded evidence
owners, not a newly asserted Login root cause. Desktop remainder stays in the
two existing Desktop feature/release matrices. Security work stays with the
two lockfiles and existing dependency/container policy scripts; no gate or
security remediation starts in this handoff.

**Stop at R6-D independent review.** Structural/native subitems and measured
installed behavior are ready for review; local installation protection is HOLD
and overall delivery remains BLOCKED as stated
above. R5/R6-B/R6-C accepted scope is retained, U1 remains deferred/BLOCKED,
S1/PCRE2 OPEN and merge/release NO-GO. No automatic next stage or security upgrade.

## Retained Windows closeout and R6-D preparation (2026-09-28)

Starting report/remote: `e1c89ea8375ded1501346ed8d4fa8e521932d7c6`;
previous verified R6-C source/test/package:
`b4990248a8437ac85af7236e01a2e7c71675afac`. Branch remains
`codex/r0-r1-safe-refactor`; fixed original Dev remains
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`.

**C1-W and C2-W have passed their limited Windows contracts. R6-C remains
BLOCKED / pending independent review, not ACCEPTED.** R5 and the limited R6-B
scope remain accepted. R6-A/U1 remains BLOCKED and deferred, independently of
this work. No Login diagnostic, five Gradio exits or double-37 batch ran here.
R6-D preparation is complete within the owner-map scope below; implementation
and whole-project closeout have not started. S1/PCRE2 and historical protection
incidents stay open; merge/release remain **NO-GO**.

Evidence W:
`D:/PythonProject/MARA-refactor-review-20260910-01a086ff/r6c-windows-closeout/`.
The retained previous-round evidence E is
`D:/PythonProject/MARA-refactor-review-20260910-01a086ff/r6c-independent-tools-artifacts/`.
`W/execution.jsonl` preserves commands, exits, source HEAD and working-file hashes.
The 135 protected local modifications are excluded from committed CI inputs.

| Scope               | Owner / contract                                                                              | Actual evidence and status                                                                                                          |
| ------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| R5                  | Accepted cache, Notebook/Session/artifact, download/FD, writer and ZIP services               | ACCEPTED scope and all historical failures/double-37 retained; no lifecycle redesign                                                |
| R6-B                | Launch construction vs manager process lifecycle; native delivery                             | Limited ACCEPTED at `eb36a61c`; platform, installer and feature limits retained                                                     |
| R6-A/U1             | Browser interaction / async tail ownership                                                    | BLOCKED and deferred; NOT RUN in this round                                                                                         |
| C1-W                | Complete stdio operation on an explicit owned Proactor loop only for Windows Selector callers | Python 3.10.11 and 3.11.9 each 93/93 MCP contracts; no cancellation watchdog rescue; limited contract PASS                          |
| C2-W                | Installed console apply on the disposable account's actual authorized Known Folder            | Both aliases, legal edit, stale skip, input preservation, output/session reload and missing-session exit; both Python versions PASS |
| C2/C3 retained      | Existing deck/export, R5 artifact registry, benchmark CLI/runner/scoring                      | Previous b499 real conversion/artifact/miniature benchmark evidence retained; no claim of a new miniature experiment                |
| R6-D preparation    | Existing R0/R6 plan, owner/import/facade map, package and Desktop capability matrices         | Targeted 15-module review and four-package map complete; no moves, renames or facade deletion                                       |
| Delivery / security | Current complete gates, native artifacts and fixed policies                                   | Final results recorded below; functional evidence does not close security or historical incidents                                   |

### C1-W: complete-operation ownership and cancellation

The public surface affected is existing MCP discovery and `MCPTool` sync/native
async execution. `mcp.py` retains public functions, schema, formatting, old
`initialized_session` patch consumers and the already-corrected `_run_async`
business-error/closed-loop behavior. `mcp_session.py` remains the SDK connection,
initialize and context-exit owner. New `mcp_operation.py` contains only the
Windows Selector/stdio bridge, with standard-library dependencies. It does not
import an agent, configuration manager or SDK transport, and introduces no connection/worker pool framework.

The coroutine factory executes inside one owned thread, explicit Proactor loop
and owner task. Connection, initialization, call and context exit stay there;
no live session, stream, Future or AnyIO cancel scope crosses loops. The first
caller cancellation is forwarded to the owner; later cancellations do not
interrupt cleanup. The caller awaits a real thread join before propagating
cancellation or the original business error. Linux, normal Proactor and SSE
operations remain on the caller loop. Global loop policy and SDK source are
unchanged; no external call is retried.

Red characterization `dc33330e` retained the real held stdio failure requiring
the ten-second rescue watchdog, while SSE passed. `aefa7d62` separately corrected
the observation boundary before production fix `780a3a57`: an instantaneous
PID-absence assertion had conflated context/thread completion with OS descendant
exit. Both failures and `stdio-exit-trace.json` remain. The trace distinguishes
the SDK launcher process from the owned service PID; a zero-time `psutil.wait`
snapshot was not accepted as proof of a still-running child.

The final tests independently wait at most five seconds for owned service
processes and then require PID absence, before a subsequent real call. This
does not kill, retry or rescue them. The live Windows 3.10/3.11 evidence records
zero-second OS observations and empty watchdog event lists, same owner
task/loop/thread at context entry and exit, dead worker threads, unchanged caller
policy and a successful later call. The existing full-suite held-stdio test also
passes locally after other imports select a Selector policy. Naked SDK Selector
failure remains upstream historical evidence; the SDK was not altered.

The 13 worker controls cover one business exception, cancellation before owner
registration, repeated cancellation during cleanup, owned background-task exit,
loop creation/shutdown/final-close failures and primary/secondary error priority.
Final `loop.close()` failure was first red at `14d4f7d8` (one FAIL, one PASS), then
fixed separately in `1ea396a3`; it no longer escapes an unobserved worker thread
or turns into a successful result. Secondary diagnostics log exception types,
not private payloads. Linux worker-mechanics controls that substitute a local
loop factory are explicitly distinct from native Windows Proactor evidence.

An additional shutdown boundary was red at `a294194c`: event-loop shutdown
cancels every Task, including the private Task previously wrapping the thread
join. Its already-cancelled shield then looped without completion. The bounded
child recorded `held=true`, two pending tasks and owner cleanup, but still
required watchdog termination; owner cleanup was not misreported as whole-thread
exit. `89e1c388` independently changes that join to a shielded executor Future,
which is not a child Task. The test now proves all-task cancellation, owner
cleanup, real thread completion, executor/loop close and unchanged global policy.
The watchdog is rescue-only and any timeout fails. All 13 worker controls pass;
the same regression is included in the real Python 3.10/3.11 93-case runs and the
complete local suite. No SDK, policy, pool or application protocol changed.

`W/windows-delivery-shutdown-verified.json` verifies hosted run
[36381339973](https://github.com/262412/MARA/actions/runs/36381339973), attempt 1,
jobs `108797554450` (3.10) and `108797554255` (3.11), at
`f659007ee9693fb9f8603850ccfbbd00f56ff5cc`. Each job is 93 PASS / 0 FAIL / 0 SKIP.
Source, fixture, OS-wait and once-only/closed-loop patch contracts are retained.

### C2-W: actual default-path installed consoles

The disposable hosted Windows 2022 account is `runneradmin`. Before any business
import/write, the fixture resolves its actual Known Folder
`C:/Users/runneradmin/AppData/Local` and authorizes only the fresh exact subtree
`C:/Users/runneradmin/AppData/Local/Cinnamon/MARA` (including `Cache`). It does not
infer this from HOME, change a registry value or authorize the local user's path.
`authorization.json` records the run/SHA and owner marker before fake data writes.

Four newly built wheels are installed non-editably in an independent venv.
The controller keeps the original account environment and imports no business
code. Separate prepare, console and verify producers each enable the unchanged
original isolation entrypoint before business imports. Public default
`SlideSessionStore()` APIs prepare the fake sessions; actual `MARA.exe apply`
and `MARA-cli.exe apply` execute from an outside-repository Unicode cwd without
PYTHONPATH, editable imports or a global console command.

Each alias applies exactly `slide-1/shape-2/text`, skips the stale
`slide-1/shape-3/text` before-text mismatch, leaves the input hash unchanged and
reloads the edited PPTX. Saved default-path sessions are completed with the
expected output path and `final` then `apply` events. A missing session exits 1
and creates no output. Guard receipts prove all three console producers close;
verification checks their OS PIDs are absent. Collection runs only after prepare
and verify processes exit, refuses live or unclosed producers/changed ownership,
copies evidence first, then removes only the owned exact subtree.

The ten local refusal/collection controls pass. Both hosted Python versions
produce console exits `[0, 0, 1]`, valid reloads and successful exact-scope cleanup.
Independent artifact reading checks PPTX XML, saved sessions/events, input hashes,
four wheel hashes per platform and the affected shipped modules. Windows checkout
CRLF differs from some Git LF blobs: the first raw-byte comparison failure is
retained, and the corrected comparison records both hashes and permits only
CRLF-to-LF normalization. It does not claim those raw bytes are identical.

All unsuccessful CI setup attempts remain: `36376240257` rejected an invalid
`runner.temp` job-env context before jobs started; `36376409981` and `36377074335`
each had two failed jobs after 90 MCP passes. The latter recorded the exact
pre-import Known Folder scope refusal. The fix gives each business producer its
own guard and preserves the controller's original environment. It does not
weaken the guard or claim the failed child recorded its exact rejected path.

The successful one-off workflow also exposed the unchanged repository runner
policy: its new workflow name was not an approved Windows runner entry. This
caused three root-policy test failures and stopped coverage in first Quality
`36376270969`. After retaining the successful hosted artifacts and workflow
definition, `60b01340` removes only that completed task-owned workflow. No runner
allowlist, scanner, baseline, required job or threshold changes. The retained
contract scripts/tests remain; 50 workflow/supply-chain/fixture controls now pass.
Reusing the hosted evidence is supported by an exact Git diff: removal of that
workflow is the sole change from e8df to 60b. For the later shutdown fix, the
identical retained task workflow was temporarily restored at `f659007e`, executed
once, then retired at `5474ec2c`. That retirement is again the only hosted-to-gate
difference; source/test/package inputs match. The final 50 policy/fixture controls
pass, with no allowlist exception.

### Current gates and platform limits

Final gate input is `5474ec2c7f49f72cc5b66ae645522fb16e6ef554`.
`W/shutdown-frozen-inputs.json` binds all seven changed source/test/harness files
and the external execution harness; `W/shutdown-execution-bindings.json` binds
the actual hosted/native and Quality revisions. Report-only delivery will retain
the same non-report tree and record its own SHA in `W/final-delivery.json`.

New [Quality 36382385122](https://github.com/262412/MARA/actions/runs/36382385122),
attempt 1, executes that final input. The actual completed result is **13 success / 7 failure**: all functional, build, static, clean-wheel and coverage jobs pass; six security gates and the required aggregate fail.
`W/shutdown-quality-evidence.json` records each actual job ID, conclusion,
test summary and finding. No unchanged SHA was redispatched.

| Current candidate verification                | Actual result                                                                                                                                             |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Linux kotaemon 3.10 / 3.11                    | Each 476 PASS / 10 existing SKIP; MCP old public/patch/error/HTML contracts included                                                                      |
| Linux ktem                                    | 3,989 PASS                                                                                                                                                |
| Benchmark and root contracts                  | 1,664 PASS                                                                                                                                                |
| slide_cli                                     | 162 PASS (72 + 72 + 18 successful progress records); original aliases retained                                                                            |
| Frontend / browser security                   | 40 Node tests and 8 security browser cases PASS; this is not U1 acceptance                                                                                |
| Static/hygiene/baseline/collection            | PASS; existing hooks, ratchet and policy unchanged                                                                                                        |
| Four distributions and clean-wheel installs   | Four wheels plus four sdists built; four clean installations PASS                                                                                         |
| Current package provenance                    | All eight downloaded artifacts match declared digests/provenance; nine shipped module bytes match Git, including exclusion of the protected local overlay |
| Original package/fixed-Dev/increment coverage | PASS: package floors 90/70/60/50 unchanged; all three diff measurements exceed the unchanged 90% gate                                                     |

| Measurement             | Executed statements | Percent | Unchanged floor |
| ----------------------- | ------------------- | ------- | --------------- |
| benchmark               | 17,146/19,005       | 90.22%  | 90%             |
| slide_cli               | 2,358/2,878         | 81.93%  | 70%             |
| kotaemon                | 7,985/11,074        | 72.11%  | 60%             |
| ktem                    | 43,808/51,906       | 84.40%  | 50%             |
| fixed-dev               | 2,608/2,702         | 96.52%  | 90%             |
| r6c-increment           | 188/191             | 98.43%  | 90%             |
| windows-round-increment | 97/99               | 97.98%  | 90%             |

Coverage job `108800646281` and `W/shutdown-coverage-summary.json` bind these
measurements to 5474. Fixed Dev is adab3f4d; whole R6-C increment starts at c5d9bb7f;
this Windows increment starts at e1c89ea8. No coverage omit/source/threshold
changes. The current increment still has unmeasured lines 15/17 in
`mcp_operation.py`; whole R6-C also includes `mcp_session.py:21`. These are
retained gaps, not a claim of complete line coverage. Functional cancellation,
ownership and installed-console outcomes above are independently asserted.

`W/shutdown-python-artifacts.json` and
`W/shutdown-report-and-workflow-package-exclusion.json` bind the current packages
and show that report/one-off workflow files are excluded from all eight archives.

Actual security output is **14 findings per dependency profile** (root 3.10,
root 3.11, container 3.10), and **4 per container profile** (lite, full, ollama),
relative to the unchanged frozen baselines. Comparison of finding identities
against prior b499 Quality 36308167603 shows zero additions and zero removals.
These remain failing security gates; “zero since previous round” is not “zero
relative to baseline.” `W/shutdown-security-comparison.json` retains exact
identities. S1/PCRE2 and the required aggregate remain open/NO-GO; no baseline,
alias, lock, allowlist, scan range, required job or threshold was changed.

The first Quality 36376270969 at 3fcf remains **10 success / 10 failure**,
including six static mypy errors, the temporary-workflow runner-policy failures
and coverage stopped by those policy failures. Typing repairs at 18ae796d /
b228be50 and the separately recorded workflow retirement fixed those input
issues. Preceding Quality 36378454108 at 60b completed **13 success / 7 failure**,
including successful package/diff coverage; it is retained as a preceding
candidate result and is not substituted for the shutdown-fix run above.

The new Windows complete kotaemon execution at f659 is **459 PASS / 4 FAIL /
23 existing SKIP**. `W/windows-node-ledger-shutdown.json` compares all four
failure nodes and their nature against preceding evidence: one absent POSIX
`os.mkfifo`, three `WinError 1314` symlink-privilege failures. No added failure
node/nature is present, and held stdio plus loop-shutdown cancellation pass in
that same complete run. Earlier Windows 456/4/23 and 458/4/23 remain historical.
Other full Windows ktem/root/CLI suites and full Windows mypy were not repeated;
`W/historical-windows-additional-nodes.json` retains the additional worktree,
bootstrap, fresh-DocQA, QASPER and permissions failures by exact node/nature.
They are not folded into a generic old 99+4 label or counted as current passes.
Linux-target mypy on the five changed Python files passes; this is distinct
from a complete native Windows mypy run.

Fresh native [36381343652](https://github.com/262412/MARA/actions/runs/36381343652),
attempt 1, is **3/3**, executed at f659: Windows 2022 job `108797569433`,
Ubuntu 22.04 packaging/smoke `108797569703`, and the same Linux package on
Ubuntu 24.04 `108799401008`. Both build platforms ran existing npm verification:
110 Electron, 41 renderer and 5 packaging tests pass. Frozen Sidecar and
Electron directory smoke cover authenticated IPC/HTTP, existing business
operations, explicit fault/cancel/retry cases and actual exit. The recorded
retry scenarios are intentional contract cases, not reruns of a failed matrix.
Original native 36308169995 at b499, intermediate 36376274298 at 3fcf and
36377872887 at e8df remain historical; none substitutes for this new build.

All five new native artifact downloads match declared GitHub digests.
Independent package inspection matches every shipped file name/size/hash
against the CI inventory: Windows 2,663, Linux 2,096 including 32 resolved safe
links. No prohibited runtime/config/test file names or escaping links are found;
bundled Punkt/tiktoken resources are present. Identified owned processes
remaining: zero. Unclassified access-denied host processes remain explicitly
13 Windows / 151 Linux, not claimed as inspected or owned. Defender reports no
detections for the actual Windows directory. The first read-only artifact/log
downloads hit TLS timeouts; distinct download attempts and original hashes are
retained, with no CI rerun.

| Native delivered item                       | Actual SHA-256                                                     |
| ------------------------------------------- | ------------------------------------------------------------------ |
| Windows GitHub artifact ZIP                 | `88625f1bc69fa9eb45781f85366715c6871317b1c419b230253d7392473c917c` |
| Linux GitHub artifact ZIP (contains tar.gz) | `3c9471c49fe9906f8b57d27b359527be69276fb602b9d73ad6176959f68a46da` |
| Windows frozen Sidecar executable           | `322a866ec62e134cf6d19b09f2ff4eb05cb5c49b20efbdb35fbb6bfa44709f47` |
| Linux frozen Sidecar executable             | `1a007a862d04e4f305c0c2c06d6243c4a3299c71e150e7e9f9ce9506883864d4` |

`W/shutdown-native-artifact-index.json`, `W/shutdown-native-smoke-outcomes.json`
and `W/package-inspection/36381343652/` retain complete provenance and outcomes.
These are source/frozen-Sidecar/Electron-directory and named OS results.
Installers, clean VM, macOS and unfinished Desktop features remain NOT VERIFIED
or unimplemented according to the retained capability matrix; no whole Desktop
or U1 browser acceptance is inferred.

### R6-D independent preparation

Preparation reuses the original R0 tracked map, R1 location plan, R6 remaining
matrix and `docs/desktop/feature-parity-matrix.md` /
`docs/desktop/release-and-acceptance-plan.md`. `W/r6d-preparation-shutdown.json`
records 15 committed candidate modules and their imports/definitions; it excludes
the protected working overlay. `W/entry-and-package-map.json` records the four
distribution declarations. The original 2,436-file inventory remains historical.

| Original plan area              | Current owner and retained boundary                                                           | Preparation conclusion                                                                                                                                        |
| ------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1 shared selection             | `ktem_contracts/file_selection.py`; original runtime/ChatPage adapters                        | Normalize and merge intentionally differ in coercion/order; retain contracts and compatibility callers                                                        |
| R2 runtime/bootstrap            | Shared Runtime and bootstrap services; lazy CLI entry groups                                  | Accepted boundaries remain; no new bootstrap, repository or DI layer                                                                                          |
| R3 Web event workflows          | Event modules and real Gradio input/output contracts                                          | U1 separately BLOCKED/deferred; keep DOM/component/patch identities                                                                                           |
| R4 planning/execution/benchmark | Existing planning/evidence owners, benchmark CLI/runner/scoring                               | Cohesive modules remain; no mechanical extraction, prompt or frozen-data change                                                                               |
| R5 lifecycle                    | Accepted cache, Notebook/Session/artifact, download/FD, writer and ZIP owners                 | Preserve authorization, transactions, generation and resource contracts                                                                                       |
| R6-A inspection                 | `docqa_inspection`; Runtime facade keeps factory/profile/acceptance subprocess and re-exports | No reverse facade dependency found; import-capability owner stays separate                                                                                    |
| R6-B Desktop                    | `sidecar-launch` constructs command/cwd/env; manager owns spawn/token/port/generation/stop    | Launch module has no manager/spawn dependency; reuse `mergeSidecarEnvironment`                                                                                |
| R6-C tools/deck                 | MCP facade → complete operation → SDK session; deck → external export                         | One connection/initialize owner; no copied SDK transport, pool or new generic framework; original types/IDs/patch seams remain                                |
| Public/package/resources        | `MARA` and `MARA-cli` → `slide_cli.cli:main`; four existing distributions/resources           | Retain internal `slide_cli`, public aliases and dynamic patch/classpath consumers                                                                             |
| Desktop capability              | Original feature-parity/release matrices                                                      | Notes/Studio/Graph/export/full resource UI remain incomplete; installer/clean VM, native picker/drag, IME and secure storage remain distinct acceptance items |
| Security/history                | Existing locks, baselines, aliases, required jobs and evidence                                | S1/PCRE2 and historical protection remain open; no whole-project closeout                                                                                     |

No broad move, rename or compatibility deletion is proposed. Conditional
external-provider, converter, GPU/Slurm and dataset capabilities are not relabelled
as verified. R6-D can review these independent inputs without reopening U1.

### Protection, provenance and review stop

Only the seven named task source/test/harness paths and this report differ from
the e1c89ea8 committed baseline. The temporary hosted workflow was retired
without widening policy. `W/policy-and-change-scope-shutdown.json` verifies the
explicit net diff, disjoint protected paths and unchanged locks, security
baselines, Gitleaks configuration, hygiene baseline and workflow gates.

Before this report write, `W/pre-report-protection-summary.json` confirms:

| Domain                               | Current round observation                                                                              | Historical status / limit                                            |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| 135 original protected modifications | Every recorded byte hash matches; the 136th currently modified tracked file is this task's report      | No user file staged or restored                                      |
| `NUL`                                | Original hash matches                                                                                  | Retained untracked                                                   |
| Canonical `.venv`                    | 98,853 recorded entries; metadata inventory matches the initial and previous delivery snapshots        | No synchronization; task-exclusive environment used                  |
| Real three config files              | Current hashes and metadata match this round's initial snapshot and the earlier post-incident snapshot | Historical writer UNKNOWN; original pre-incident bytes UNVERIFIED    |
| Real two DB files                    | Recorded size/mtime metadata matches                                                                   | No claim of a new full byte-level DB audit                           |
| Real theflow cache                   | 610 entries; metadata inventory matches this round                                                     | Historical 614→610 incident remains OPEN; no restore or cleanup      |
| User office cache                    | Zero entries, unchanged metadata inventory                                                             | Real office profile not used                                         |
| Historical reports/evidence          | Earlier report tail retained byte-for-byte; task output confined to W and owned fixtures               | No repeat investigation, automatic restoration or historical cleanup |

This is forward protection against the recorded post-incident baseline, never
a total historical protection PASS. Private config bytes were used only for
local protection hashes and were not printed or loaded by a task runtime.
No credentials or full environment were printed; no real MCP configuration
was connected. CI fixture cleanup
was confined to authorized disposable-account resources after producers exited.

| Identity                                                      | Actual revision                                       |
| ------------------------------------------------------------- | ----------------------------------------------------- |
| Round start                                                   | `e1c89ea8375ded1501346ed8d4fa8e521932d7c6`            |
| Previous R6-C verified candidate                              | `b4990248a8437ac85af7236e01a2e7c71675afac`            |
| Final production source change                                | `89e1c388443f34f64901e779608d01681e9d3427`            |
| Last ownership test change / red                              | `a294194ca590b01c407259fcba2b939a3a4dd1d3`            |
| Final default-apply fixture/harness change                    | `e8df3ec37b3f85949282171c3f625848d899359f`            |
| Actual Windows/native execution tree and package builds       | `f659007ee9693fb9f8603850ccfbbd00f56ff5cc`            |
| Final source/test/harness tree and Quality/four-package input | `5474ec2c7f49f72cc5b66ae645522fb16e6ef554`            |
| Report-only, local and remote final SHA                       | Recorded after commit/push in `W/final-delivery.json` |

`W/delivery-revisions-pre-report.json` preserves the complete small-commit
chain and each changed file's last revision. `W/final-delivery.json` binds the
report commit to an identical non-report Git tree, the frozen source/test/harness
hashes, actual CI attempts and downloaded artifacts. Final secret scan and the
post-report per-domain protection comparison are recorded in
`W/final-secret-scan.json` and `W/final-protection-summary.json`; report-only
reuse does not waive either check. No force push, branch/worktree creation,
merge, deployment, release or safety/coverage policy change occurred.

**C1-W and C2-W limited validation passed; R6-D independent preparation is
complete. R6-C remains BLOCKED / pending independent review, not ACCEPTED.**
U1 stays deferred. R5 and limited R6-B acceptance remain. Historical protection
and S1/PCRE2 stay open; merge/release remain NO-GO. Work stops at this independent
review point; no R6-D implementation or U1 investigation starts automatically.

### Retained independent R6-C review (2026-09-27)

Baseline: `c5d9bb7f20fa2db5b5a893cb2dcc96de0762e767`; branch:
`codex/r0-r1-safe-refactor`; fixed original Dev:
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`.

The user accepts **R6-B at `eb36a61ceb5e03d3a916d567d5e08037597950a9`**
only for its implemented scope, actual artifacts and verified Windows Server 2022,
Ubuntu 22.04 and Ubuntu 24.04 platforms. Its retained review below predates that
acceptance. Installer, clean-VM, macOS and missing Desktop feature limits remain.
**R5 stays ACCEPTED. R6-A/U1 stays BLOCKED and deferred, independently of R6-C.**
No Login diagnostic, five Gradio exits or original double-37 batch runs here.
R6-D is outside this round.

**R6-C is BLOCKED, not ACCEPTED.** The newly demonstrated Windows MCP stdio
cancellation failure remains open. Independent deck/artifact and miniature
benchmark contracts are verified within the limits below; they do not erase that failure. No dependency,
permission, schema, global event-loop policy or transport replacement is added
to bypass it. S1/PCRE2 and historical protection incidents stay separate;
merge/release remain **NO-GO**.

Evidence root E:
`D:/PythonProject/MARA-refactor-review-20260910-01a086ff/r6c-independent-tools-artifacts/`.
`execution.jsonl` records commands, exits, source HEAD and protected local overlay
hashes. Commit receipts stage named files only. CI packages use committed inputs,
not the 135 protected local modifications.

| Scope    | Owner and contract                                                                    | Actual evidence / remaining limit                                                                                          | State                               |
| -------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| R5       | Existing graph-cache, Notebook/artifact, download and writer services                 | Previously accepted scope and original failures/double-37 retained; no R5 redesign                                         | ACCEPTED                            |
| R6-B     | Launch configuration, manager process ownership and native delivery                   | Reviewed `eb36a61c`; platform/installer/feature limits retained                                                            | ACCEPTED, limited                   |
| R6-A/U1  | Original browser interaction and exit contracts                                       | Historical failure remains; no U1 execution in R6-C                                                                        | BLOCKED / deferred                  |
| C1       | MCP facade / BaseTool / agent factories; SDK session ownership                        | Red/fix contracts and real stdio/SSE pass in supported runs; Windows Selector cancellation fails even directly through SDK | BLOCKED                             |
| C2       | Deck content operations vs external PDF conversion; existing R5 artifact registration | Real conversion, installed commands and explicit-root service pass; Windows default CLI session-write path unverified      | Limited contracts verified          |
| C3       | Existing CLI, runner, cache, scoring and reporting                                    | Own seven-command manifest chain, 35 local model calls; deterministic contract checks pass                                 | Limited contracts verified          |
| Delivery | Related suites, static, wheels, coverage, Quality and native artifacts                | Final native 3/3; functional Linux/static/build/coverage gates pass; Quality 13 success / 7 failure                        | Evidence complete; security BLOCKED |

### C1: unchanged facade, fixes and session extraction

`agents/tools/mcp_session.py` owns the existing SDK stdio/SSE connection,
`ClientSession.initialize()` and context exit. SDK imports stay lazy. The original
MCPTool, discovery/call functions, configuration shape, schema, text assembly,
unsupported-transport behavior and real patch seams stay at `mcp.py`. No server,
pool or general plugin framework is introduced.

Characterization first: 41 existing cases passed; the expanded old-tree run
reported **23 PASS / 3 FAIL**. `_run_async` incorrectly caught a business
`RuntimeError` and tried to reschedule the already-consumed coroutine, masking the
original error; the business call counter remained one. Commit `416b1008` confines exception
handling to loop selection and propagates the single business result/error.
Commit `e75c9ccf` separately escapes remote tool names/descriptions in HTML while
retaining the original description truncation. Their follow-ups passed 25 and
52 cases. Extraction is separate at `84100457`.

Final compatibility review found that the first bridge fix omitted the original
closed-current-loop fallback. The frozen original function passes the two new
closed-loop cases; `865ca7c9` fails both before executing the operation. Red tests
are committed at `212c62e0`; the two-line selection fix is separately committed
at `b4990248`. It chooses a fresh loop only when the selected loop is closed,
without changing global loop policy or catching business exceptions. The stable
28-case bridge/session/HTML regression passes at `b4990248`. A preceding 28-pass
run overlapped a newline-normalizing hook and is retained as preliminary, not a
frozen-input proof. The hook-only failure and the subsequent clean static run are
retained too.

Real agent consumers exposed a second defect: `enabled_tools` was popped from a
shared configuration dictionary. The six failing regressions (plus one passing
control) precede `a3946a1d`, which copies the entry dictionary in ReAct and ReWOO
before consuming it; all seven then passed. Manager/config ownership and the
existing shallow-copy contract are retained.

Own stdio and authenticated-free loopback SSE fixtures perform actual SDK
discovery, BaseTool and agent calls, argument/schema checks, errors, cancellation,
connection/early-exit failures and process/port cleanup. They never open user MCP
configuration or contact user servers. The corrected extraction group passed
**74/74** on the task Python's initial Proactor policy. The earlier nine-case run
had a vacuous stdio early-exit fixture; corrected command indexing and a server
started receipt precede the valid two endpoint tests. The vacuous run is retained
and is not credited as early-exit evidence.

The full Windows suite subsequently imported `duckduckgo_search`, whose locked
installed initializer selects `WindowsSelectorEventLoopPolicy`. Under that policy,
SDK 1.12.4 uses its subprocess fallback. `FallbackProcess.wait()` waits through a
shielded AnyIO worker thread; cancellation cannot interrupt that wait while the
server is held. The original full batch was **INTERRUPTED** (exit 15, 498.53 s),
not passed. Its live stack, PID creation times/commands, held evidence and retained
runtime are in `mcp-interrupted-*` and `mcp-held-live-stack.txt`.

The test-only watchdog at `c2d9982a` starts after the held point, records recovery,
verifies the owned fixture command, kills/waits only that server and explicitly
**fails** the test if recovery was needed. It does not count kill or cleanup as
successful cancellation. The controlled MARA Selector case failed. A direct SDK
case bypassing the extracted module also failed; the separately labelled
child-only Proactor control passed. The SDK code path plus live stack and these
controls support a Windows SDK/event-loop limitation, not a new transport fix.
An explicit supported cancellation solution without dependency/global-policy
changes remains the next bounded design question. No such solution is claimed.

SSE has a separate limit: cancelling the local call closes its client connection,
but the held server producer can remain until fixture shutdown. The receipt
distinguishes client cancellation from fixture/server completion and makes no
remote rollback guarantee. All recovered owned processes are checked for OS exit.

### C2: deck publication and existing artifact services

`deck.py` retains deck DTOs, target IDs, snapshot/read/edit ordering and
`before_text` matching. `deck_export.py` owns external conversion. Public export
and existing `deck.os`, `deck.shutil`, `deck.subprocess` patch consumers still
resolve to the actual objects used by conversion.

Two old-tree red cases proved that a successful converter exit with no new PDF
could return an old destination PDF. The separate fix `effccff1` allocates a
unique owned conversion directory, requires the newly produced PDF, then replaces
the destination. Extraction follows at `de83dadb`. Original source checks,
converter selection, flags, timeout and return type remain. Only the owned
workspace is removed; a cleanup failure does not replace a primary conversion
error. Cleanup-only failure is reported even if publication already succeeded.
Twelve contract cases, five resource cases and the 26-case extraction group pass;
the final C2/C3 test correction group passes **16/16**. Resource tests include
same-stem concurrent conversion, timeout, denied publication, primary/secondary
cleanup failures and destination preservation. Those resource counterexamples
inject converter/OS failures; the actual LibreOffice checks below are separate,
not proof of concurrent LibreOffice profile behavior.

Actual LibreOffice **26.2.0.3 620(Build:3)** (`soffice.com` SHA-256
`1051878423572139c1deb425bb4a6cae0ef89b6aa94924201c50a26adc3de82d`)
uses an owned profile. Two Unicode two-slide decks produce reloadable two-page
PDFs with the expected text. The stale-output negative uses the real executable's
`--version` branch: exit zero without a PDF must reject the retained old output.
Earlier fixtures wrongly assumed plain text/empty files would fail conversion;
those failures and the earlier cleanup failure are preserved. This is not a claim
that LibreOffice rejects every malformed input.

The 18-case artifact group uses the production registry's 14 types, real SQLite
Notebook storage and `save_answer_note`, export registration, reload and deletion.
JSON/Markdown/HTML exports, data-table CSV, infographic SVG and deck/outline PPTX
are exercised. MP3/MP4 without an adapter fail as designed. Public read is not
Notebook write; schema failure leaves no registration. Removing a record retains
its note/source/export data according to R5 policy. Local deterministic generators
do not establish external LLM/media adapter or missing Desktop capabilities.

| Registry types                                                                                     | Actual record/generation boundary                                                   | Actual exports                                         | Not established                                       |
| -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------ | ----------------------------------------------------- |
| `study_guide`, `quiz`, `flashcards`, `mindmap`, `briefing_doc`, `faq`, `timeline`, `custom_report` | Production deterministic payload dispatcher, citations, SQL registration and reload | JSON, Markdown, HTML                                   | External model quality; U1-dependent UI               |
| `data_table`                                                                                       | Same record contract                                                                | JSON, Markdown, HTML, CSV                              | Unimplemented Desktop integration                     |
| `infographic`                                                                                      | Same record contract                                                                | JSON, Markdown, HTML, SVG                              | External image/media generation                       |
| `slide_outline`, `slide_deck`                                                                      | Same record contract                                                                | JSON, Markdown, HTML, reloadable PPTX                  | General layout fidelity or all Office renderers       |
| `audio_overview`, `video_overview`                                                                 | Script/record contract, media not ready                                             | JSON, Markdown, HTML; missing MP3/MP4 adapter rejected | Actual audio/video generation and binary media export |

The initial and final four-wheel sets were installed non-editably in the task environment.
Outside-repository Unicode cwd runs actual `MARA`/`MARA-cli` help and read commands;
module hashes resolve to these wheels with no source PYTHONPATH. The initial
installed probe completed 12 console commands, then constructing the default
Windows slide session store tried a Known Folder outside the test root. The
existing guard denied `os.mkdir` **before access**. No CLI `apply` ran, no guard
was relaxed, and the immediate forward protection receipt passed. The default
Windows CLI session-write path is **NOT VERIFIED** in this environment.

A separate explicit-owned-root installed service applies one valid edit and
skips one stale `before_text`, reloads the completed session and preserves the
input deck. Actual console inspection and real PDF export then pass; missing-input
and no-new-PDF paths return exits 2 and 1. That service test is not represented as
console `apply`. See `installed-deck-explicit/receipt.json` and its cleanup receipt.

After the final bridge fix, all four wheels and sdists were rebuilt from the
`b4990248` archive into `r6c-final-dist`, checked and reinstalled with no active
task-environment consumer. The final installed probe repeats explicit-root
apply/reload, real console inspection/PDF export, old-PDF rejection and missing
input exits, and also executes the closed-loop bridge from the installed module.
It passes with no PYTHONPATH and two PDF pages. The default Known Folder path is
not attempted again. See `final-local-build.json`, `final-installed-inputs.json`
and `installed-deck-final/receipt.json`; the earlier wheel hashes remain history.

### C3: existing benchmark modules retained

No production extraction was needed: existing CLI/runner/scoring responsibilities
remain. A subprocess imports the existing runtime isolation entry before business
code, uses an eight-example owned Unicode manifest and a deterministic local model
only at `_resolve_llm`. Real CLI parsing, text reading, retrieval, cache, runner,
prediction serialization, scoring and reports execute. No model training,
prompt/route tuning, frozen data rewrite or remote model service is involved.

The stable retained run at `726d7e6d` passes **7 commands / 35 model calls**:
warm-first, warm-second, cold, bypass, alias/sample/shard/limit, rescore and budget.
IDs/order, six successful answers, one refusal and one error, denominator eight,
source identity, absent emitted citation/page annotations, route and generation
budget are checked. Seed 7 / shard 1 of 2 / limit 2 yields `ex-7`, `ex-4` in order.
Rescoring leaves original artifact bytes unchanged. Windows records a late model
return as timeout; it does not provide POSIX signal interruption. Raw reports and
hashes remain under `D:/MARA-s1-01a086ff/r6c-benchmark` and E's candidate receipt.

All fixture failures remain: child-held cache handle cleanup before process exit,
wrong refusal phrase, conflation of retrieval with emitted citation, and a deep
Windows evidence path causing cold-cache MAX_PATH failures. The stable fixture
uses a shorter owned path and removes only its child runtime after verified OS
exit. Command output-name collision avoidance schedules each command once in the
next timestamp slot; it never reruns a failed invocation.

### Delivery checkpoint, input identity and protection

Runtime source last changed at `b4990248a8437ac85af7236e01a2e7c71675afac`.
The first complete source/test/package input is
`b01030c25b41bae509f5e267b2ffc8a62fc7022c`; subsequent changes through
`726d7e6da2415acf65c2b6b3db33cf0a9c690a21` are tests only. The later closed-loop
fix changes runtime inputs, so `final-frozen-inputs.json` freezes the complete
`b4990248` source/test/package candidate and records the new native rebuild.
Test corrections are separate from production fixes. The report/remote receipts identify the
final delivery commits; no report-only reuse is inferred without input comparison.

| Boundary                  | Characterization / red                            | Minimal fix                               | Extraction / evidence                                                         |
| ------------------------- | ------------------------------------------------- | ----------------------------------------- | ----------------------------------------------------------------------------- |
| MCP loop and HTML         | `74829165`                                        | `416b1008`, `e75c9ccf`                    | `84100457`; real-service tests `1ce2705a`, corrected early-exit `4fb5ed59`    |
| Agent config ownership    | `0484d783`                                        | `a3946a1d`                                | Existing managers and ReAct/ReWOO retained                                    |
| MCP cancellation          | Interrupted complete batch and direct SDK failure | No production workaround; remains BLOCKED | Failing watchdog test `c2d9982a` preserves failure and permits owned recovery |
| Closed-loop compatibility | `212c62e0`; frozen original passes both cases     | `b4990248`                                | Stable 28-case group and final installed-wheel probe                          |
| Deck publication          | `1679759d`                                        | `effccff1`                                | `de83dadb`; test typing `e2c354ae`                                            |
| Artifact registry         | `f69a78b5`                                        | No production change                      | Existing R5 services retained                                                 |
| Benchmark CLI             | `b01030c2`                                        | No production change                      | Test helper split `726d7e6d`                                                  |

All full SHAs, ordered commits and file lists are recorded in the commit receipts
under E; these short labels are not substitute source identities. The final
source/test/harness/package SHA is the full `b4990248...` value above.

Local four-wheel/four-sdist builds and twine checks pass from a committed Git
archive, without the protected local overlay. Because the archive lacks `.git`,
its version fallback is `0.0.1`; this is not the CI Git-versioned wheel identity.
Installed probes use those four local wheels. The dependency environment is
task-owned and reused; fresh clean-wheel installation is separately tested by CI.
Local `npm run verify` passes; no canonical environment synchronization occurs.
Final native CI also reruns the complete verify command: Electron **110/110**,
Renderer **41/41**, packaging **5/5**, Sidecar **150 PASS / 2 existing SKIP**,
schema comparison, TypeScript and production builds. The existing Vite chunk-size
warning remains; no budget or dependency changes hide it.

New native Gate2 [36304969812](https://github.com/262412/MARA/actions/runs/36304969812),
attempt 1 at `b01030c2`, completes **3/3**. Its Windows 2663 / Linux 2096 file
inventories exactly match downloaded names/sizes/hashes and identify no remaining
owned processes. This first R6-C run remains historical after `b4990248`.
Final Gate2 [36308169995](https://github.com/262412/MARA/actions/runs/36308169995),
attempt 1 at `b4990248`, also completes **3/3**. It rebuilds the frozen Sidecar and
Electron directory, then exercises actual authenticated IPC/HTTP, index/query,
cancellation/recovery, persistence/restart, storage-fault and exit scenarios.
Those are the existing native smoke contracts, not U1's deferred browser matrix.

The final Windows 2663-file and Linux 2096-file/link inventories exactly match
downloaded paths, sizes and hashes. Both ASARs contain 96 entries; manager, launch
and main compiled modules match current compilation. No forbidden config/runtime
test names or invalid package links were found. Identified owned processes
remaining: **0**. Access-denied unrelated processes remain unclassified (Windows
14, Linux 153); this is not a whole-host process-absence claim. Windows Defender
reported no detections within its scanned artifact scope. Four benign hidden
dependency files are retained and explicitly classified in native resources.
See `package-inspection/36308169995`, `final-native-smoke-outcomes.json` and the
native run's diagnostics. Windows Server 2022 / Ubuntu 22.04 / Ubuntu 24.04 results
do not prove installer, clean-VM, macOS or unimplemented Desktop features.

| Final native job | Platform / actual scope                                                                                               | Result |
| ---------------- | --------------------------------------------------------------------------------------------------------------------- | ------ |
| `108588784444`   | Windows Server 2022: verify, PyInstaller Sidecar + Electron directory build, native business/resource smoke, Defender | PASS   |
| `108588784511`   | Ubuntu 22.04: verify, PyInstaller Sidecar + Electron directory build, native business/resource smoke                  | PASS   |
| `108590100413`   | Ubuntu 24.04: reuse the same final Ubuntu 22.04 artifact and run portability smoke; not a third build                 | PASS   |

| Final artifact, `b4990248`            | SHA-256                                                            |
| ------------------------------------- | ------------------------------------------------------------------ |
| Windows downloaded artifact ZIP       | `5a587fa362c91cf1bd28b5af89d1817d723af8b54f3155938b3dadc6997130ae` |
| Linux downloaded artifact ZIP         | `92b910a63aadf76f5741ac3ff903d830eb7c4916af4c23b9271315aa35bcc166` |
| Windows frozen Sidecar executable     | `bb6aac1a177fadbf345cd4993c899c241036a109e9cdac7bbccf8d001d222da1` |
| Linux frozen Sidecar executable       | `15928145fadaa19b099d47409c1a5780c70eaa095a0f0299091fc9e0c23772fc` |
| CI four-wheel/four-sdist evidence ZIP | `44801c355687981a995098558cc7c8a4b0e3b0f813bb24b2374c89ba529575fc` |

The CI distributions use actual version `0.0.40`. Eight hashes match their index
and provenance subjects; all provenance declares `b4990248` and run 36308167603.
The changed wheel modules and two protected local Python overlays match committed
source bytes, confirming that the user overlays were not packaged. See
`final-python-artifacts.json` for every distribution hash. This checks the
downloaded evidence and declared provenance; it does not claim a new signature.

Initial Quality [36304965711](https://github.com/262412/MARA/actions/runs/36304965711),
attempt 1 at `b01030c2`, completes FAILURE with **12 successful / 8 failed jobs**.
It has a real new static failure: test function length, a test
type-narrowing omission and this report's table formatting. The first two fixes
are `726d7e6d` and `e2c354ae`; report formatting is corrected independently.
Coverage completed naturally before the registered 60-minute collection bound;
no cancellation was sent. It reports benchmark **90.22%**, slide CLI **81.93%**,
kotaemon **71.90%**, ktem **84.40%**, fixed-Dev diff **96.47% (2517/2609)**.
These are `b01030c2` results, not measurements of the later two-line bridge fix.
Final Quality [36308167603](https://github.com/262412/MARA/actions/runs/36308167603),
attempt 1, runs on `b4990248` with the same fixed-Dev base. It rebuilds all four
distributions: two sdists include modified tests, so those old sdists are not
claimed equivalent. It completes **FAILURE: 13 successful / 7 failed jobs**.
Static is now successful. The seven failures are three dependency audits, three
container supply-chain jobs and the unchanged required aggregation, not seven
new R6-C product defects. Final snapshots, all 20 job logs and per-job outcomes
are in `final-quality-complete-36308167603.json` and `final-quality-evidence.json`.

Final coverage job `108588779182` passes the original package floors:

| Package   | Actual statement coverage | Original floor |
| --------- | ------------------------- | -------------- |
| benchmark | **90.22%** (17146/19005)  | 90%            |
| slide CLI | **81.93%** (2358/2878)    | 70%            |
| kotaemon  | **71.90%** (7899/10986)   | 60%            |
| ktem      | **84.40%** (43808/51906)  | 50%            |

Fixed original Dev diff coverage is **96.48% (2519/2611)**; R6-C increment from
`c5d9bb7f` is **99.00% (99/100)**, both against the unchanged 90% rule. These use
the final CI measurement, SHA-256
`5a8a75deca49f60aabfd07d89e180fd4d2188cbedf2a50b5b04a67b83e87b17b`
for `coverage.json`. The coverage artifact ZIP digest is
`ca69c729d1c2ca95413e2d6fb768dd9a9bb71ffa2b4b302ad24c0893acdc6706`.
See `final-coverage-verified.json`, including uncovered lines. The first local
postprocessing child omitted its parent's UTF-8 flag and failed decoding a git
diff with GBK; those logs and the failing analysis receipt remain. Explicit
`-X utf8 -B` child invocations then verify the same measured numbers. No test
suite or CI run was repeated for that analysis-command correction.

Final Linux job evidence at `b4990248`: kotaemon Python 3.10 and 3.11 each report
**459 PASS / 10 existing SKIP**; ktem **3989 PASS**; benchmark/root **1654 PASS**;
slide CLI completes successfully. Static/hygiene/baseline ratchet, full configured
Linux mypy, unified collection, fresh four-wheel installations, distribution
checks and repository/image secret scans pass. Frontend security tests and its
eight browser smoke cases pass; those eight are not the original U1 double-37.

The six completed security scan jobs still fail. Each root-py310/root-py311/
container-py310 dependency audit lists **14 findings relative to its frozen
baseline**; each lite/full/ollama image lists **4**. Exact sets match the reviewed
R6-B run **36299641983**: **0 added / 0 disappeared since R6-B** in each job.
The container set is AnyIO CVE-2026-63374 and PCRE2 CVE-2026-86145, CVE-2026-89157,
CVE-2026-89161. Per-job identifiers and all dependency findings are preserved in
the evidence JSON and raw logs. This comparison does not waive those failures;
S1/PCRE2 remain OPEN and required-job aggregation is unchanged.

Windows full suites retain their actual outcomes: ktem **3892 PASS / 97 FAIL**;
benchmark/root **1607 PASS / 10 FAIL / 37 existing SKIP**; slide CLI has one
protected-user-skill failure while the committed-archive CLI suite passes. The
original 99 Windows nodes remain with the same normalized primary errors; nine
additional full-repository Windows failures are listed separately in
`windows-node-comparison.json`. Five are missing symlink privilege, one assumes
POSIX site-packages layout, and three concern POSIX launcher/shell execution;
the raw empty-output bootstrap failure does not identify its precise failed shell
operation. No extra failure is silently assigned to the old 99.
Final bounded kotaemon at `b4990248` is **441 PASS / 5 FAIL / 23 existing SKIP**:
the four old capability failures have the same nature, plus the held-stdio
Selector cancellation failure. It is a complete failed batch, not a pass assembled
from the Proactor control. No skip/omit/allowlist is added.
The other complete Windows package batches above ran at `b01030c2` with the
recorded protected local overlays; they are not relabelled as fresh `b4990248`
executions. The changed bridge is covered by the final full Windows kotaemon
batch and the final full Linux suites. Full Windows mypy's prior platform limits
remain unverified here; current Linux mypy does not close them.

Forward receipts compare all **135 protected raw file hashes**, NUL, canonical
environment metadata (**98,853 entries**), cache metadata (**610**), office cache
(**0**), protected config bytes and runtime DB metadata. Both the receipt after
the denied default-path access and `pre-final-report-summary.json` pass. This does not establish old contents:
historical writer **UNKNOWN**, original content **UNVERIFIED** and cache event
**OPEN** remain unresolved. No history scan without a lead, restore, timestamp
adjustment or real-cache cleanup is performed.

The report-only delivery uses a separate post-commit receipt rather than embedding
its own commit hash in the file. `final-delivery.json` is the authoritative
source/test/package/report/local/remote map. It checks that the entire committed
tree except this report matches `b4990248`, all 35 frozen external helpers are
unchanged, the remote equals local HEAD, the index is empty and only the original
135 user modifications plus NUL remain. Its final scan references
`final-secret-scan.log` / `final-secret-scan.json` at that exact report commit;
`final-protection-summary.json` records the final per-domain comparison. Missing
or failed receipts must not be interpreted as delivery completion. No report-only
CI rerun or old binary is represented as a new source execution.

Stop at the **R6-C independent review point**. C1 remains BLOCKED on supported
Windows Selector cancellation/termination; the next minimal question is how to
complete that held-stdio cancellation contract without changing global policy,
SDK dependencies or the transport architecture. No solution is claimed from
the passing child-only Proactor control. C2's default Windows console session
write additionally needs a supported explicit root or an isolated OS profile to
verify; the pre-access refusal is not product success. C3's local-model contracts
do not establish external provider quality. R6-D and U1 investigation do not
start automatically. R5 and limited R6-B acceptance, historical protection
incidents, S1/PCRE2 OPEN and merge/release NO-GO remain separate.

## Retained independent R6-B review (2026-09-27)

Baseline: `dfeda2335b7e8f37b8361ca5c5578561c57bb583`; branch:
`codex/r0-r1-safe-refactor`; fixed original Dev:
`adab3f4d8f221e3620494fab0a24ef8e5557d12a`.

The user explicitly deferred R6-A/U1 without making it a prerequisite for
independent R6-B/C. **R6-A/U1 remains BLOCKED; R5 remains ACCEPTED.** This
supersedes only the earlier scheduling restriction, not its failures or gates.
This round runs no Login diagnostic, Edge/Chromium comparison, Gradio five-exit
group or original double-37 browser batch. No R6-C/D or security upgrade starts.

**R6-B limited verification passed; awaiting independent review. R6-A/U1 stays
BLOCKED and does not block independent subsequent tasks. R6-B is not ACCEPTED.**
Overall CI remains FAILURE for the security gates described below. Runtime source last
changed at `61e995f66ca2f0d35c6ed40a1779ceaf8a5cb89c`; current source/test/native
package candidate is `eb36a61ceb5e03d3a916d567d5e08037597950a9`.

Evidence root E is
`D:/PythonProject/MARA-refactor-review-20260910-01a086ff/r6b-independent-desktop/`.
`execution.jsonl` records command, exit, HEAD and local modified-file hashes;
commit/push receipts retain the exact paths. Native CI uses clean committed
inputs; the 135 protected local edits remain uncommitted and are not silently
included in those packages. `portable-candidate-inputs.json` fixes all eight
changed non-report files. R6-B changes no Python wheel-package inputs.

### B1: launch configuration ownership and unchanged entrypoints

`electron/sidecar-launch.ts` now owns development Python selection, packaged
command paths, working-directory selection and environment assembly. It imports
only `node:path` and the existing `mergeSidecarEnvironment`. It neither spawns nor
imports the manager, Click, Gradio or a complete application/runtime. The manager
keeps child/token/port/generation/startup/restart/stop, mkdir/spawn, settings
snapshotting, authentication and ready/health/doctor validation. Original
`sidecarCommand()` and `developmentPython()` patch seams remain real consumers.

Characterization precedes extraction: 13 new launch cases plus the existing
manager/smoke/data contracts pass **35/35 before and 35/35 after extraction**.
They retain explicit Python strings verbatim, then workspace `.venv`, then the
platform fallback; exact packaged executable/arguments; inherited versus trusted
environment precedence; forced config/data/cache/settings/temp and parent-pipe
values; development PYTHONPATH order; smoke fault behavior; missing settings and
synchronous exception timing. No real token/key or complete environment is logged.
`main`, `smoke-environment` and `desktop-data` retain their existing responsibilities.

### B2: actual process ownership, red tests and minimal fix

The old manager dropped ownership after calling kill, before OS exit. Real child
tests exposed **1 PASS / 2 FAIL** for startup stop and failed-ready cleanup.
An intermediate implementation still returned a stale `starting` result
(**31 PASS / 1 FAIL**, despite its historical log label ending in `green`).
The expanded termination-failure counterexample then exposed a false healthy
state (**16 PASS / 1 FAIL**). All failures and working-input hashes are retained;
they are not rewritten as clean-commit passes.

The fix shares one shutdown operation, makes a concurrent start wait for it,
keeps child ownership until exit acknowledgement, rejects a termination that did
not finish, and preserves primary startup errors alongside secondary cleanup
errors. Intentional failed-start cleanup cannot schedule an automatic restart.
The existing HTTP shutdown/grace period remains; termination now waits up to two
seconds after normal kill and two after forced kill for actual exit. The ready
deadline, HTTP timeouts and 250/500/1000 ms restart budget are unchanged. No IPC,
HTTP, SSE, task schema, settings policy or global concurrency protocol is rewritten.

The resulting related local suite is **52/52**. Its 17 real-process cases cover
segmented/invalid/oversized ready, cold startup, PID/protocol/revision/fingerprint,
startup exit/stop, missing executable, original ready timeout, shared stop/start,
queued restarts without PID overlap, late old-generation callbacks, automatic
restart exhaustion, parent EOF, authenticated HTTP and closed listening ports.
The forced-termination negative case keeps the live child owned and status failed;
cleanup then proves its actual exit. A kill return or `stopped` label is never the
sole exit proof.

Two additional owned Windows tests, executed at `61e995f6`, exercise production
`sidecar.server_runtime.wait_for_parent_pipe` with and without a heartbeat. Both
pass; the launcher and actual interpreter PID are independently absent afterward.
The first ad hoc observer failure assumed those PIDs were equal and is retained;
it did not capture the values and is not claimed as a product failure or a pass
of the separate historical pytest node. `runtime-input-equivalence.json` proves
the runtime/dependency inputs are unchanged in `eb36a61c`; packaging evidence was
rebuilt separately. No canonical environment was synchronized.

### B3: native delivery defects and evidence boundaries

The first new native run at `61e995f6` passed **3/3**, but review found two gaps:
Ubuntu cleanup listed Python PIDs 6871/8976 without module identities, and the
Windows download contained 2659 files versus 2663 in the native package. A separate
read-only receipt records package file hashes and only scoped process identities,
without full command lines or environments.

The receipt run at `4c5a1f6e` is retained as **1 SUCCESS / 1 FAILURE / 1 SKIPPED**.
Ubuntu identified two remaining `sidecar.smoke_embedding_server` fixtures, PIDs
6741/8829 with parent 1; Windows had no identified owned process remaining. This
proves the controlled fixture defect, not the identities of the earlier two PIDs.
The shell background PID belonged to a subshell rather than the model process;
three existing POSIX launchers now use `exec`, so their existing kill/wait owns
the producer. The Windows artifact omitted four hidden resource files, totaling
858 bytes, including python-docx's `.rels`. Existing package-path upload now
includes hidden files; no safety baseline or source/config allowlist was widened.

At `ebff72df`, the next native run passed **3/3** and both scoped process lists
were empty. Windows archive count/size matched the 2663-file native inventory.
However, strict archive inspection found **32 Linux symlinks pointing to absolute
CI build paths**. That is a real relocation contract failure despite the old smoke
success. `artifact-relocation-red.json` retains all targets. Installed
`@electron/packager 20.0.4` copies `extraResource` with default `fs.cp` symlink
rewriting. The minimal packaging fix copies the Sidecar in `afterComplete` with
`verbatimSymlinks: true`, preserving PyInstaller's relative library links. Native
inventory now rejects absolute/outside/unresolved links; Ubuntu 24 checks the
extracted archive for broken links before running the existing business smoke.
No Electron/Node/Python dependency is upgraded. An earlier local streaming-tar
reader error is retained separately; fixing that observer did not rerun an App.

| Native run / attempt                                                       | Input      | Actual result and meaning                                                            |
| -------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------ |
| [36297185458 / 1](https://github.com/262412/MARA/actions/runs/36297185458) | `61e995f6` | 3/3; historical initial build, ownership/archive gaps remain in its evidence         |
| [36298203884 / 1](https://github.com/262412/MARA/actions/runs/36298203884) | `4c5a1f6e` | 1 success, 1 failure, 1 dependency skip; fixture ownership red                       |
| [36298731989 / 1](https://github.com/262412/MARA/actions/runs/36298731989) | `ebff72df` | 3/3; process/archive fixes pass, later Linux relocation check FAILS                  |
| [36299639434 / 1](https://github.com/262412/MARA/actions/runs/36299639434) | `eb36a61c` | 3/3; corrected package, relocation, existing business smoke and resource checks PASS |

Final job IDs are Windows **108564797828**, Ubuntu 22 **108564797911**, and Ubuntu
24 **108565602899**. Both build jobs ran the existing complete `npm run verify`:
Electron **110/110**, renderer **41/41**, Sidecar **150 passed / 2 existing skipped**,
packaging **5/5**, schema/type checks and production builds. Node was **24.21.0**,
npm **11.19.0**. Windows Defender signature **1.459.424.0** reported no detections.

Downloaded archives match their GitHub SHA-256 digests. Every file name, size
and hash matches its same-run native manifest: Linux **2096** entries including
32 relative links (1,281,503,109 bytes counting resolved link targets); Windows
**2663** files (1,003,967,743 bytes), including the four hidden resources. Linux
links resolve wholly inside the package after relocation. Both ASARs contain
96 entries, no compiled tests/source directories or checked private-config/runtime
names, and their manager/launch/main bytes match the current compilation.
Bundled tiktoken and punkt resources are present. Receipts and full inventories
are under `E/package-inspection/36299639434/`.

| Artifact                           | Download SHA-256                                                   | Frozen Sidecar SHA-256                                             |
| ---------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Linux archive, 421,182,462 bytes   | `ac53738a5c54055280fd0b21189ce98c7f39efccbda39b49d84d8ede1883dacc` | `6921822f85f421455bad2f2fecc01aa6264c35ff7447ff9be73b828478dd62fa` |
| Windows archive, 403,860,293 bytes | `2b69b9ebb02ee98006961eff6eff8e6b4919e9045622d6059f8474ff942943aa` | `9b79244fa3dae48d7b95b87883ba4224a527dbf68486c845e6e2f0ffed8d2f9f` |

Both scoped post-smoke process lists are empty. Access-denied observations remain
**144 Linux / 14 Windows**, so this is scoped ownership evidence, supplemented by
the manager's real exit/PID tests and native process exit statuses, not universal
OS-process visibility. Gitleaks scanned the extracted ASARs and inventories
(5.15 MB) with zero findings; this is not a full scan of every dependency binary.
The actual evidence scope is Windows Server 2022, Ubuntu 22.04 and the same
Linux package on Ubuntu 24.04; installed Electron 43.2.0 and frozen PyInstaller
Sidecar, not source-only HTTP. Existing smoke uses outside/read-only cwd, real
renderer IPC and authenticated loopback HTTP, ready/PID/settings handshake,
Doctor/Files/Sessions, indexing/query/citations, cancel/retry/partial results,
session CRUD, file deletion, model-route persistence/migration, single-instance,
Sidecar crash recovery and disk-full/database-lock/large-file faults.

No installer, Windows 10/11 clean VM, upgrade/uninstall, native file-picker/IME,
macOS or complete Desktop product parity is claimed. Notes/Studio/Graph/export
P0 and full Index/Reranking/MCP/user-resource/settings scope remain incomplete
under the existing feature matrix. Scoped process observations explicitly retain
access-denied counts; they do not prove visibility into every OS process.

### Stable gates, coverage and CI provenance

[Quality 36299641983 / attempt 1](https://github.com/262412/MARA/actions/runs/36299641983)
completed **FAILURE: 13 success / 7 failure** on
`eb36a61ceb5e03d3a916d567d5e08037597950a9`, with fixed Dev base `adab3f4d`.
All functional/static/build/coverage jobs passed. The seven failures are the three
dependency profiles, three container vulnerability baselines and their required
aggregate. No required job is waived and overall merge/release remains NO-GO.
The counts below are this run's results, not old cc0 evidence.

| Job IDs                                        | Current executed evidence                                                                                    | Result                            |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------- |
| `108565074616`, `108565074735`                 | Full static/hooks/hygiene/lock/baseline and unified collection                                               | PASS                              |
| `108565074727`                                 | ktem isolated runtime: 3964 passed, 140 warnings                                                             | PASS                              |
| `108565074787`                                 | Benchmark/root: 1653 passed, 8 warnings                                                                      | PASS                              |
| `108565074830`, `108565074781`                 | kotaemon Python 3.10/3.11: each 422 passed, 10 existing skips, 93 warnings                                   | PASS                              |
| `108565074808`                                 | Complete slide_cli suite                                                                                     | PASS                              |
| `108565074779`                                 | Existing Node frontend contracts and 8 browser security scenarios                                            | PASS; not the original Gradio 37  |
| `108565074814`, `108565074908`                 | Four noneditable clean-wheel installations and all four wheel/sdist builds with distribution provenance/SBOM | PASS                              |
| `108565074795`, `108565074706`                 | Repository/history and built-image secret gates                                                              | PASS                              |
| `108565074831`                                 | Original package floors and fixed-Dev production diff                                                        | PASS                              |
| `108565074757`, `108565074818`, `108565074894` | root-py310, root-py311, container-py310 dependency baseline                                                  | FAIL; 14 new findings per profile |
| `108565074785`, `108565074798`, `108565074821` | lite/ollama/full: actual built-image runtime smoke passes; vulnerability baseline fails                      | FAIL; 4 new findings per profile  |
| `108570144960`                                 | Required quality gates aggregate                                                                             | FAIL                              |

Dependency findings are anyio 4.11.0 (GHSA-5p39-cfhj-2xmp,
GHSA-82r6-8w77-94w6), chromadb 0.5.16 (PYSEC-2026-3813/3814/3815), nltk 3.10.3
(GHSA-8mgp-746c-j5xp), pypdf 4.2.0 (PYSEC-2026-3910/3911/3912/3913), soupsieve
2.8 (GHSA-gjv8-xp57-g29c, GHSA-j934-xhv5-fg8f), transformers 4.56.2
(PYSEC-2026-3929) and unstructured 0.15.14 (PYSEC-2026-3930). Container findings
are anyio 4.11.0 CVE-2026-63374 and libpcre2-8-0 10.42-1
CVE-2026-86145/89157/89161. These are per-profile baseline findings, not a global
deduplicated CVE count. Baseline/alias/G0 exceptions remain unchanged;
S1/PCRE2 stays OPEN. Full job logs and identifiers are in `final-quality-evidence.json`.

| Coverage scope               | Actual current result                 | Unchanged floor           |
| ---------------------------- | ------------------------------------- | ------------------------- |
| benchmark                    | 90.22%                                | 90%                       |
| slide_cli                    | 80.37%                                | 70%                       |
| kotaemon                     | 71.13%                                | 60%                       |
| ktem / ktem_contracts        | 84.23%                                | 50%                       |
| Fixed Dev production diff    | 96.38%, 2420/2511 statements          | 90%                       |
| R6-B increment from dfeda233 | N/A, 0/0 Python production statements | Existing policy unchanged |

Coverage was executed on current CI source. Downloaded `coverage-evidence`
SHA-256 is `c902f325abc992bbb6345727b3acb743f53759d8904cc9e50500ac1cb3f34cf1`;
the fixed-Dev and round-increment checks were also rerun locally against that
exact JSON. The helper prints 100% for 0/0; the report correctly treats it as
an empty denominator, not tested new Python code. No omit/skip/allowlist, lock,
scan scope, required job or threshold was changed. Eight freshly built Python
wheel/sdist hashes are in `current-python-artifacts.json`; no prior build is
relabeled as a current execution.

Superseded Quality runs remain separate: `36297188393` at `61e995f6` was
cancelled with **12 success / 7 failure / 1 cancelled**; `36298898967` at
`ebff72df` was cancelled with **12 success / 6 failure / 2 cancelled**. Their
coverage jobs did not finish. Existing workflow concurrency cancelled them when
new evidenced fixes required new inputs; no unchanged SHA was rerun to select
green. All native failure and success batches likewise remain separate above.

Local focused hooks and supply-chain policy pass; newline/Black/Prettier repair
attempts remain in the ledger. Local Node 24.14.0 installation recorded the
existing jsdom engine warning and one high advisory; final native CI used Node
24.21.0/npm 11.19.0. The original Windows 99, kotaemon four capability failures
and full Windows mypy platform limits remain historical and were not rerun as
those same pytest/platform groups. Native Sidecar unittest does not close them.

### Responsibilities and independent remaining work

| Owner / scope                       | Contract and evidence                                                                                                               | Status                                                            |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| R5-A                                | Existing file-deletion coordinator and ordered external-store cleanup; historical failure matrix retained                           | ACCEPTED; download ownership belongs to C3                        |
| R5-B / L1-I1 / W1-W2                | Writer/ZIP, Source lifetime and index identity, event/stale-output boundaries; original same-source double 36 retained              | ACCEPTED within reviewed scope                                    |
| R5-C                                | C1 graph cache, C2 notebook/artifact transactions, C3 DownloadWorkspace/FD/transfer/retention; same-source double 37 retained       | ACCEPTED scope unchanged; no R5-D                                 |
| R6-A / U1                           | Existing CLI inspection/identity/actor/parent-pipe and selector/focus/exit work retained; Edge154 fourth exit Login failure remains | BLOCKED, deferred; not a prerequisite for independent B/C         |
| R6-B / launch module                | Pure command/cwd/environment responsibility; original manager patch seams and launch precedence                                     | Characterized 35/35 before/after                                  |
| R6-B / manager                      | Own child until actual exit; stale-generation and restart boundaries                                                                | 52/52 related local contracts; current native suites pass         |
| R6-B / native packaging             | Frozen Sidecar/Electron composition, resource relocation, auth/business smoke, exit and hashes                                      | Current 3/3 and exact archive checks pass; earlier red retained   |
| MCP/agent, deck/artifact, benchmark | Existing adapters and command surfaces retained; live providers/datasets/converters remain conditional                              | No new features or benchmark claims; independent R6-C not started |
| Full delivery/security              | Existing CI policy, platform/VM limitations and all unresolved project work                                                         | S1/PCRE2 OPEN; merge/release NO-GO                                |

### Protection, source history and stopping point

Entry and intermediate forward checks retain all **135 protected raw files**,
NUL, three private post-incident config hashes, real DB metadata, 98,853 canonical
environment entries, 610 cache entries and office-cache metadata. Contents and
credentials are not printed. Historical writer UNKNOWN, original bytes UNVERIFIED
and cache 614 to 610 OPEN remain independent; metadata equality does not certify
unread bytes or close that history. No restoration, mtime adjustment, real-cache
cleanup, canonical sync or repeated search of historical directories occurred.
Only task roots and ephemeral native CI runners are used. The final pre-report
forward receipt matches all 135 original raw files, NUL, private config hashes
and the same domain/file metadata; the 136th modified path is this task report.
No new protection difference was found; no total historical protection PASS is claimed.

| Commit                                     | Role                                                |
| ------------------------------------------ | --------------------------------------------------- |
| `5efc9f6b008e9b8a3d553f9f7774eabde6e080ea` | Independent R6-B schedule checkpoint                |
| `792dab8cc88cec361da29e1667329b367e4a9ea6` | Old launch characterization tests                   |
| `7d0677c64761d3255615858e697de42ab25899ac` | Structural launch extraction                        |
| `bb5ede7e1423982b032f99e22adf114957e03b7c` | Real-process red tests                              |
| `f2f1106e218d126109b07d77ed8505102a3ab4da` | Expanded lifecycle tests                            |
| `61e995f66ca2f0d35c6ed40a1779ceaf8a5cb89c` | Minimal production process-ownership fix            |
| `4c5a1f6ee59d7e2f458fbbbe325aa1fb17ca9d33` | Native resource/process observation and tests       |
| `ebff72dfc071c00efe1b2005d0a0bae95ccc35a0` | POSIX fixture exec and complete Windows archive     |
| `127483c666b22e9f89460cfd1d6e1aef8aa78037` | Reject nonportable native links                     |
| `b11665c6819f20527638295a6c14d15d58e5754c` | Extracted-archive relocation gate                   |
| `eb36a61ceb5e03d3a916d567d5e08037597950a9` | Minimal Sidecar resource-copy fix; frozen candidate |

The report-only commit, final local/remote SHA, exact input-equivalence check,
and post-commit secret-scan result are recorded in `E/final-delivery.json` and the
final protection receipts. Report-only delivery does not claim a new functional
execution: source/test/native package evidence remains pinned to `eb36a61c`.
The evidence bundle retains logs/receipts/helper code; private config hashes are
excluded and large original artifacts remain at their recorded paths and hashes.
All pre-existing report history below is preserved byte for byte.

**R6-B 限定验证通过，等待独立审查；R6-A/U1 仍 BLOCKED，但不阻断独立后续任务。**
R5 remains ACCEPTED; historical protection events and S1/PCRE2 remain unresolved;
merge/release stays NO-GO. Stop at R6-B review. No automatic ACCEPTED, R6-C,
new branch/worktree, force push, merge, deployment or release occurred.

## Retained Edge154 natural acceptance at dfeda233 (2026-09-27)

**R6-A/U1 remains BLOCKED: 3 exit cases PASS, the fourth FAILS at Login,
and the fifth is NOT RUN.** This is the one natural plan authorized after
`8f20f5ae9d1d667623ec051f89f7f6891e6a0b0a`. It stopped on the first unexpected
failure. Selector/U1 browser contracts, original 37 primary, 37 confirmation,
and new source gates/Quality CI are **NOT RUN**. No retry, third batch, extra
Login/A-B diagnostic or product change was made. R5 stays ACCEPTED; R6-A is
not ACCEPTED; S1/PCRE2 remains OPEN and merge/release NO-GO.

The supplemental authorization replaced only the Edge153 pin with the existing
**Edge 154.0.4258.37**. The original preflight difference and zero-launch
checkpoint remain below as history; their pending-authorization state is now
superseded. Actual execution HEAD is
`8f20f5ae9d1d667623ec051f89f7f6891e6a0b0a`; all 133 source/test/harness hashes
match `fa8d8a276230a3d3185014a6afd88e55603651eb`. Selector fix `7f29ce87`, U1 and
R5 implementation are unchanged. This delivery changes only this report in Git.

Evidence is `D:/PythonProject/MARA-refactor-review-20260910-01a086ff/`
`r6a-u1-recovery/natural-validation/` (N). `approved-browser-input.json`,
`acceptance-plan.json` and `frozen-inputs.json` preceded every formal App.
The natural profile retains Playwright **1.61.1**, Gradio **4.39.0**, `msedge`,
headless, 1600x1200, en-US, original business observers/counterexamples and
all STABILITY/FRAME/LOGIN DIAGNOSTIC switches **0**. Normalized launch
arguments in all four runs equal the original natural launch; only owned
profile/cache roots differ. Each App used a fresh empty runtime/cache,
serial startup, exclusive port 8768 and the original timeout budgets.

### Approved files and actual loaded identity

| Input                                                          | Approved version | SHA-256                                                            |
| -------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------ |
| `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe` | 154.0.4258.37    | `f530bafcdb7e529bd21dd8be46e20c82b5c70fa0ffd770fe4c45a5c2c054c211` |
| `154.0.4258.37/msedge.dll` under that Application directory    | 154.0.4258.37    | `e14b3d725fef3eb23ef28d01d6d5707bcb6ffc3ae59ce2e42997ac72bf0674f0` |

First formal browser PID **53880** was observed at **04:24:29.605 UTC** with
that executable and mapped 154 DLL, matching both hashes. All four formal
browsers have loaded-module receipts. The failed case used Node **51968** and
browser **52748**; its module receipt was saved at **04:27:19.585 UTC**, before
Login. OS-only reads of owned process identities added no browser logpoints,
parameters, page timers or synthetic frames. Races with already-exited child
PIDs are retained as observation gaps; the main browser identity was captured.
Before/after hashes and in-run metadata monitoring found no input change.
The residual 153 DLL is not used as 154 running evidence. No browser install,
downgrade, update-service change or security-policy change occurred.

### One stopped natural attempt: original five exits

The driver started at **04:23:48.878 UTC** on 2026-09-27 (Beijing 12:23);
its execution ledger records **257.09 seconds**. `edge154-stopped-plan-analysis.json` checks saved results,
held events, identities, isolation and cleanup without launching an App.
The planned success-only five-case verifier was not executed.

| Ordered case      | Intended held/fault point                           | Current result | Actual outer / Node / App exit |
| ----------------- | --------------------------------------------------- | -------------- | ------------------------------ |
| Normal completion | Held model reached before release                   | PASS           | 0 / 0 / 0                      |
| Assertion         | Held reached, exact owned expected/actual assertion | PASS           | 1 / 1 / 0                      |
| Node watchdog     | Held reached, Node watchdog marker and primary      | PASS           | 1 / 1 / 0                      |
| App watchdog      | **Not reached; Login failed before injection**      | **FAIL**       | 1 / 1 / 0                      |
| Release failure   | Not started after fourth-case failure               | NOT RUN        | NOT RUN                        |

For the first three cases, real session/event IDs identify the held request.
Model-wait exit, generator completion, worker project frames, requests,
barriers, process exit and directory removal are separate evidence. The
intermediate model-wait receipt is not treated as generator completion;
final producer records show finished/non-executing generators and quiescence.
The fourth has no held record, App watchdog marker, queue event, server
operation, generator or model worker. Its outer exit 1 is a Login failure,
not a successful watchdog injection. All four released their UI/model/
embedding barriers, exited without forced termination, removed only their
owned roots and left no owned process or listener. The failed screenshot
remains a secondary error, separate from successful process/resource cleanup.

### Fourth-case failure layer and evidence ceiling

`edge154-exit-app-watchdog.log` records:

- **04:27:20.549 UTC:** real `locator.click` begins on Login.
- **04:27:20.553-20.554:** button resolves; visible/enabled/stable wait begins.
- **04:27:50.550:** the unchanged 30,000 ms click budget expires. No
  missing-stable, retry, scroll or performing-click record occurs in that call.
- **After saving the primary:** the existing harness's bounded main-world
  rAF check returns timeout at 04:27:52.564; the DOM snapshot reports a visible,
  focused document and button at (568, 315.375, 464, 40), opacity 1, with no
  reported animations. These are post-failure observations.
- **04:27:55.572:** screenshot times out after 3,000 ms, after fonts loaded.
  GPU command-buffer messages at 04:27:55.769/770 occur during browser close,
  after Login failed; they do not establish its cause.

The actual utility `evaluateInUtility -> checkElementStates -> stable/rAF -> resolve/reject` return chain was not observed in this natural profile. No
utility frame/context/node/action identity or first callback record is claimed.
The evidence locates a pre-Login mouse actionability stall; it does not
distinguish a utility return-chain, scheduling, context or product cause.
There is no evidence-based product fix in this round. **Edge154's current
candidate failed; Edge153's historical Login problem remains UNATTRIBUTED.**
Neither the first three passes nor similarity of the fourth failure proves
that upgrading fixed the old problem or that both failures share a cause.
The next minimum step is independent disposition of this saved failure and
its missing utility-return evidence. No further run is automatically opened.

### Forward protection and delivery boundaries

Entry and every before/after-App checkpoint match all **135 protected raw
files**, NUL, three restricted post-incident config hashes, real database
metadata, **98,853** canonical-environment entries, **610** cache entries and
office-cache metadata. Config contents/hashes stay private; metadata checks
do not certify unread file contents. The original isolation guard ran before
business imports in every launcher/App; resolved config/data/cache/settings/
database/temp/profile paths stayed under the owned root. No new protection
difference was found. Historical config writer **UNKNOWN**, original bytes
**UNVERIFIED**, and cache **614 to 610 OPEN** remain independent. No new
historical clue, repeated historical scan, restoration, mtime adjustment or
real-cache cleanup occurred. Forward protection does not close that history.

Prior results remain separate: fd44 primary **37/37**, confirmation **16 PASS /
1 FAIL / 20 NOT RUN**; original R5 same-source double 37/37; earlier natural
exits **4 PASS / 1 FAIL**; e15 instrumented Edge/Chromium **5/5 + 5/5**; fa8 Node
**160/160**. None substitutes for the current unexecuted selector/U1 or
double-37 acceptance. No cross-version/profile/source/batch results are joined.

Report-only equality is checked against frozen source/test/harness, 17
dependency inputs and protected bytes. Existing package/coverage evidence
stays scoped to `cc0bb3a3ec83bca6932a431dc766bb1713749050`; native Desktop
Gate 2 stays `48affef7e0504f63286793c571f6167c3fa82d69` (3/3, scoped).
Quality **35816144107**, cc0's **13 success / 7 failure**, is historical only.
No new Linux/Node, build, clean-wheel, coverage, Desktop or Quality execution
is claimed after this failed prerequisite. Windows99, kotaemon4 and Win32
mypy limitations retain their existing records. Browser154 does not certify
Desktop or installation behavior.

N's `edge154-report-commit.json`, `edge154-ordinary-push.json` and
`edge154-delivery.json` record actual report/local/remote SHAs, report hooks,
final secret scan, final protection, archive identity and unchanged-input
proof. Only this report is staged/committed. No branch/worktree creation,
force push, merge, deployment, publication, architecture split, dependency/
safety/coverage-policy change or R6-B work occurred. Delivery remains
**BLOCKED for independent R6-A review**, not functional acceptance.

## Retained natural-validation preflight at 8f20f5ae (2026-09-27)

**R6-A/U1 remains BLOCKED before the first App launch: the required Edge
binary changed.** At baseline `988c698336b64782ea75f2acc258b56030544078`, the
source/test/harness bytes still match `fa8d8a276230a3d3185014a6afd88e55603651eb`,
but the installed `msedge.exe` now reports **154.0.4258.37**, versus the
previously pinned **153.0.4234.48**. This is a new browser-input preflight
difference, not a new Login test failure and not part of the old configuration
or cache incident. There have been **zero App/browser launches** this round.

The user now authorizes one natural plan without requiring another historical
failure or unique attribution first: original five exits, direct selector/U1
contracts, original 37 primary, then same-input 37 confirmation. Its proposed
natural profile sets STABILITY_DIAGNOSTIC, FRAME_DIAGNOSTIC and
LOGIN_DIAGNOSTIC to **0**, retaining original business observers and
counterexamples, Edge channel, headless mode, 1600x1200 viewport, en-US locale,
original launch arguments and timeout budgets. `preflight-plan.json` retains
the original six fixture lists/order and budgets. It is explicitly marked
**browser input not approved**, not an executed frozen acceptance candidate.
All five exits, selector/U1 browser checks, both 37 batches and new Quality
are **NOT RUN**. No Login/A-B diagnostic or retry was added.

Evidence is `D:/PythonProject/MARA-refactor-review-20260910-01a086ff/`
`r6a-u1-recovery/natural-validation/` (N). `browser-input-difference.json`
records the read-only comparison:

| Browser input                                                  | Prior pin                                                          | Current observation                                                |
| -------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe` | 153.0.4234.48                                                      | 154.0.4258.37                                                      |
| EXE SHA-256                                                    | `9a84277c86316b975e5927a12f2355001b2e46f274c7a61b2fa0278aaf435996` | `f530bafcdb7e529bd21dd8be46e20c82b5c70fa0ffd770fe4c45a5c2c054c211` |
| Versioned 153 DLL                                              | Pinned existing file                                               | Still present, hash equal                                          |
| Versioned 154 candidate DLL                                    | Outside the prior pin                                              | `e14b3d725fef3eb23ef28d01d6d5707bcb6ffc3ae59ce2e42997ac72bf0674f0` |

The 154 DLL value is a file observation, not evidence of a loaded browser.
No browser was started merely to obtain a new identity. File timestamps do
not establish the update writer or installation time; those are **UNKNOWN**.
The other eleven previous runtime-file hashes, including Playwright **1.61.1**,
Gradio **4.39.0** and the old 153 DLL, still match. Keeping an old DLL does not
make the new launcher equivalent. No system browser was changed, downgraded,
replaced or launched by this task.

Changing the target to current Edge 154 requires an explicit browser-input
decision because the user fixed the original actual binary and the supplied
prompt's section 3 requires a preflight difference before changing it. That
choice was requested with the concrete difference available; no approval has
been inferred. If current Edge is authorized, it must be re-pinned before the
first natural case, with every original first-failure/no-third-batch rule
retained. Until then, the minimum blocked step is binary-input disposition,
not another attempt to reproduce Login.

The 133 source/test/harness hashes, dependency inputs and all 135 protected
raw files match the preceding delivery. NUL and the three restricted
post-incident config hashes match; real database metadata, 98,853 canonical
environment entries, 610 cache entries and the office-cache metadata match.
These metadata comparisons do not certify unread file contents. No owned
task process or listener on 8768 was found. No true config/data/cache was
restored or cleaned, and no timestamp was changed. Historical config writer
**UNKNOWN**, original bytes **UNVERIFIED**, and cache **614 to 610 OPEN** remain
independent; there was no new historical clue or repeat historical search.

`retained-input-equivalence.json` verifies the prior A evidence archive's
SHA-256 and all 318 members/CRC, and confirms source/dependency equality.
It explicitly rejects browser-input equivalence. Prior e15 instrumented
Edge/Chromium **5/5 + 5/5**, fa8 Node **160/160**, the earlier natural **4 PASS /
1 FAIL**, and all prior 37 results remain their own executions. No new tests,
Linux, build, clean-wheel, coverage, Desktop or CI execution is claimed here.
Package/coverage evidence remains scoped to **cc0bb3a3**, Native Gate 2 to
**48affef7**, and Quality **35816144107** to cc0's actual **13 success / 7
failure**. A changed system browser is not proof of current Desktop behavior.

This checkpoint changes only the current report. Report-only source/test/
package input equality, report hooks, final secret scan, forward protection
and ordinary-push identities are recorded separately in N's delivery receipt.
R5 stays ACCEPTED; R6-A is not ACCEPTED. S1/PCRE2 stays OPEN and merge/release
NO-GO. No R6-B/C/D, new branch/worktree, force push, merge, deployment,
publication or policy/baseline/coverage change is authorized or performed.

## Retained actual utility-call diagnostic checkpoint (2026-09-26)

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
