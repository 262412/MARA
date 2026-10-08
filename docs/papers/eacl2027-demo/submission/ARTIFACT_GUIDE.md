# LMDoc artifact and deployment guide

This submission positions LMDoc as an observable document-QA workbench. It does not claim that automatic routing improves QA accuracy or that its heuristic verifier guarantees factual correctness.

LMDoc is the name used in the paper. The software, original video and screenshot, executable commands, and historical records retain the release name MARA. Links and verbatim outputs below preserve those actual identifiers.

## Public artifacts

- Software release and installation guide: https://github.com/262412/MARA/releases/tag/v0.0.40
- Windows x64 reviewer installer: https://github.com/262412/MARA/releases/download/v0.0.40/slide-app.zip
- Installer checksum: https://github.com/262412/MARA/releases/download/v0.0.40/slide-app.zip.sha256
- Repository: https://github.com/262412/MARA
- Existing user-workflow video: https://youtu.be/owRaHCzSVNg
- Released synthesis asset: mara-full-system-benchmark-synthesis-v0.0.40.zip

The paper and this guide distinguish the video deployment from the benchmark deployment. The recording uses Deepseek/Google APIs and displays the packaged UI label 0.0.18. The benchmark uses Qwen3-8B/bge-m3, with ColQwen and a configured local Qwen3-VL backend for selected comparison configurations. v0.0.40 identifies the repository release and synthesis distribution. These identifiers are not evidence of an identical executable build.

## Windows reviewer installation

Download `slide-app.zip`, extract the whole archive, then double-click `Install.cmd` and `Start.cmd`. Allow at least 8 GB of free space. The installer provisions Python 3.10.19, pinned binary dependencies, and the included application wheels. First installation requires internet access to GitHub and PyPI; it does not require an existing Python, Git, CUDA, or compiler for the included runtime. It is not an offline model bundle.

Configure a chat model and an embedding model in the Web UI resources tab, then index `samples/reviewer-note.txt` and follow the example questions in the package README. No credentials or model weights are supplied. Data, configuration, and logs remain in the extracted directory's `runtime` folder. Keep the folder in place after installation.

The replacement installer is 33,918,912 bytes and has SHA-256 `886b949135ce74f123e0ae7b8a81c533594f0e98739b8057c277485ec3fb1432`. It is based on main commit `dfcca9987fa4f4d3c5e4da303217c32692032b65` plus installation fixes, with application source commit `e6afa5dcda18ef6d5d6aae2efb0f1a6b806187b3` and package version `0.0.41`. Its internal directory is `MARA-reviewer-windows-x64-e6afa5dc`. This updated installation artifact is hosted on the historical release page; it did not produce the paper's original benchmark numbers.

Verified on Windows: isolated installation with Python/Git absent from the process PATH, CLI checks, HTTP/UI startup, repeat installation preserving config/data, and checksum-failure handling. The new Harbor case additionally validates real-model indexing/QA in this Windows package. A separate fresh-runtime repetition fails strict verification even after source correction; both runs are retained. Other operating systems have not been validated. In the package directory, use:

```powershell
.\MARA.cmd app doctor --json
.\MARA.cmd docqa index .\samples\reviewer-note.txt
.\MARA.cmd docqa files
.\MARA.cmd docqa ask --help
```

## Historical tagged source

The v0.0.40 tag still identifies `37487f35610076c1016e1b59d3bf982388d1a275`. To inspect that historical source in a standalone checkout:

```shell
git clone --branch v0.0.40 https://github.com/262412/MARA.git
cd MARA
```

Replacing the release ZIP does not update the Git tag. A fresh Windows `uv sync --extra mara` check on 23 September 2026 failed building `llama-cpp-python==0.2.7`, brought in by `kotaemon[all]`, because `nmake` and C/C++ compilers were missing. This is not a portable reviewer quick-start command. The new ZIP avoids that optional backend. The historical README's `pip install mara-research-cli` route was also unavailable on PyPI and TestPyPI when checked on 22 September 2026.

Provider checks alone do not establish end-to-end readiness. The source installation failure is recorded separately from the successful updated ZIP installation; no new benchmark was run.

A fully local setup requires local providers for all selected operations. Hosted generation or embeddings can transmit document content to a provider. The benchmark's two A100 or two L40S GPUs per shard are allocated experimental resources, not measured minimum hardware requirements for the application.

## What the video demonstrates

The unchanged recording shows the workbench under the release name MARA. The paper now calls it LMDoc; this naming change does not add scenes or change the recorded build.

Source selection, page preview, questions over a text document, citations, and route/retrieval/verification status. It does not demonstrate VLM reasoning, graph retrieval, recovery, or abstention. The paper reports those limitations explicitly. The existing video is retained unchanged; the author confirms its duration is 150 seconds.

## Scope of reproducibility

The synthesis contains 41 run/shard artifact sets, represented by ledger/manifest entries, and 3,540 metric records for 1,090 dataset--question pairs. It supports aggregate, pairing, route-count, and bootstrap checks. It does not include generated answers, effective per-job route manifests, actual per-answer generation-path traces, or per-job source commits. It therefore does not by itself support an exact end-to-end rerun or diagnosis of the cause of SlideVQA's identical scores.

The original synthesis ZIP is included unchanged in the supplementary submission package. REPRODUCTION.md explains the numerical checks. The source code is Apache 2.0 with Kotaemon attribution; dataset terms remain separate. The historical release NOTICE retains the earlier product name Slides.

## Original Harbor walkthrough

Open `case_study/walkthrough.html` in the supplementary ZIP. It presents a complete
source-scope diagnosis and links directly to original inputs, provider outputs,
intermediate/displayed answers, effective settings, and decisions. Run
`python case_study/verify_case.py` for the offline audit without API credentials.

The constructed Harbor case uses the installed reviewer build, Deepseek generation
and OpenAI embeddings. It is separate from the unchanged six-dataset benchmark.
The captured first pair corrects an unresolved question by selecting the data
policy. A second run in a fresh environment still abstains because strict verification
rejects extra generated explanation; its raw records are included, not discarded.
This demonstrates inspectability, not reliable recovery. It does not fill the old
SlideVQA provenance gaps. The original video and public links stay unchanged.

## Follow-up: verifier repair and actual visual input

Start with `review_followup/walkthrough.html` and `review_followup/README.md`.
The added records compare the original raw answer with decision stages, isolate
a supported-policy false rejection, include its source patch and five live
pairs, and show a real NOAA/NASA chart intervention with an image-removed
control. Run `python review_followup/verify_followup.py` for the offline audit.
The patch is separate from the original installed release. All preliminary
failures are retained. Neither user efficiency, automatic recovery nor restored
historical SlideVQA output provenance is claimed. The video remains unchanged.
