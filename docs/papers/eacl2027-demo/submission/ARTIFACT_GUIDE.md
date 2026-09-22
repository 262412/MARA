# MARA artifact and deployment guide

This submission positions MARA as an observable document-QA workbench. It does not claim that automatic routing improves QA accuracy or that its heuristic verifier guarantees factual correctness.

## Public artifacts

- Software release and downloadable source: https://github.com/262412/MARA/releases/tag/v0.0.40
- Repository: https://github.com/262412/MARA
- Existing user-workflow video: https://youtu.be/owRaHCzSVNg
- Released synthesis asset: mara-full-system-benchmark-synthesis-v0.0.40.zip

The paper and this guide distinguish the video deployment from the benchmark deployment. The recording uses Deepseek/Google APIs and displays the packaged UI label 0.0.18. The benchmark uses Qwen3-8B/bge-m3, with ColQwen and a configured local Qwen3-VL backend for selected comparison configurations. v0.0.40 identifies the repository release and synthesis distribution. These identifiers are not evidence of an identical executable build.

## Tagged source installation

Use a fresh standalone source checkout, with its own environment. The v0.0.40 README's package-index route, pip install mara-research-cli, is not available on either PyPI or TestPyPI as checked on 22 September 2026. Use the documented source route instead:

~~~shell
git clone --branch v0.0.40 https://github.com/262412/MARA.git
cd MARA
uv sync --extra mara
~~~

Prepare .env from .env.example according to the tagged README and configure the chosen model and embedding providers. For source-mode startup:

~~~shell
uv run --no-sync python app.py
~~~

After dependencies and providers are configured, representative commands are:

~~~shell
uv run --no-sync MARA --help
uv run --no-sync MARA docqa doctor
uv run --no-sync MARA docqa index ./example.pdf
uv run --no-sync MARA docqa files
uv run --no-sync MARA docqa ask --file example.pdf --reasoning mara --prompt "Summarize this document"
~~~

These are release-specific source instructions, not a report of a new clean-install test. The present revision did not install dependencies, download models, or execute a new index/query run. Provider checks alone do not establish end-to-end readiness.

A fully local setup requires local providers for all selected operations. Hosted generation or embeddings can transmit document content to a provider. The benchmark's two A100 or two L40S GPUs per shard are allocated experimental resources, not measured minimum hardware requirements for the application.

## What the video demonstrates

Source selection, page preview, questions over a text document, citations, and route/retrieval/verification status. It does not demonstrate VLM reasoning, graph retrieval, recovery, or abstention. The paper reports those limitations explicitly. The existing video is retained unchanged; the author confirms its duration is 150 seconds.

## Scope of reproducibility

The synthesis contains 41 run/shard artifact sets, represented by ledger/manifest entries, and 3,540 metric records for 1,090 dataset--question pairs. It supports aggregate, pairing, route-count, and bootstrap checks. It does not include generated answers, effective per-job route manifests, actual per-answer generation-path traces, or per-job source commits. It therefore does not by itself support an exact end-to-end rerun or diagnosis of the cause of SlideVQA's identical scores.

The original synthesis ZIP is included unchanged in the supplementary submission package. REPRODUCTION.md explains the numerical checks. The source code is Apache 2.0 with Kotaemon attribution; dataset terms remain separate. The historical release NOTICE retains the earlier product name Slides.
