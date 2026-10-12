# LMDoc follow-up diagnostics

Open **walkthrough.html** for the evidence and comparison. This is an offline
record viewer, not a new native application interface or an edited video.
Harbor is an author-constructed fictional task executed with real providers;
the chart is a real public NOAA/NASA report page. Both are new cases, separate
from the historical six-dataset benchmark. All preliminary failures are retained.

## What the observations establish

- The raw Harbor answer already points to the missing policy. Additional logs
  do not establish an easier user workflow than displaying that explanation.
- The recorded policy explanation was wrongly rejected. Identical-claim replay
  isolates a regular-inflection mismatch. The patch fixes that check; it does
  not turn a heuristic lexical verifier into a general factuality guarantee.
- Five predeclared patched-source pairs return the policy's duration five times
  and abstain without the policy five times. The unpatched verifier also accepts
  the five newly generated policy claim strings. Do not describe these live
  counts as a measured before/after improvement.
- In the direct-reading chart case, auto selects text and returns approximately
  -50%. A manual page-image selection sends an actual image to the same model
  and returns approximately -40%, matching the plotted endpoint. Removing only
  the image from the same generation request yields -50%. This is one observed
  component contrast, not general visual accuracy or automatic recovery.
- Historical SlideVQA raw answers and execution paths have not been restored.

## Read and audit without models

From the supplementary archive root:

```shell
python case_study/verify_case.py
python review_followup/verify_followup.py
```

Both checks use the Python standard library and no API. The second checks the
manifest, all ten Harbor outcomes, request differences, retained failure,
same-input verifier comparison, actual visual model/input, byte-identical image,
and image-removed request. It checks saved observations, not a new model run.

The original case remains in `../case_study`. New files are grouped into
`harbor/`, `visual/`, and `preliminary-slot-failure/`. The chart source is
[NOAA/NASA, Annual Global Analysis for 2023, page 9](https://www.nasa.gov/wp-content/uploads/2024/01/noaa-nasa-global-analysis-2023.pdf).
The excerpt preserves that page; its local PDF page number is 1. The human
reference is an approximate visual reading, not underlying measurement data.
Large full-runtime responses use lossless `.json.gz` compression; the
offline verifier reads them directly. Standard gzip tools can extract the
unchanged JSON, and the viewer shows the relevant answer strings without extraction.

## Source repair and deterministic verifier replay

The original Windows installation is unchanged. Follow-up execution uses its
Python/dependencies with source from `e6afa5dc` plus `verifier-repair.patch`.
The new repair commit is `9472e9e1`; it is not claimed to be in the released ZIP.
Use a separate checkout to avoid changing your existing application:

```shell
git clone https://github.com/262412/MARA.git LMDoc-case-source
cd LMDoc-case-source
git checkout e6afa5dcda18ef6d5d6aae2efb0f1a6b806187b3
git apply /path/to/review_followup/verifier-repair.patch
```

Use the installed reviewer's Python (`runtime/environment/Scripts/python.exe`)
for the runtime-dependent scripts. Omit `--source` to replay using that original
installed code; supply the patched checkout to replay using the repair:

```shell
python review_followup/replay_verifier.py
python review_followup/replay_verifier.py --source /path/to/LMDoc-case-source
```

These commands do not retrieve or generate. They join exactly the recorded
verification claim strings, use the captured evidence and request, and call
the verifier. This isolates the check; it is not a full guardrail/UI replay.

## Fresh execution with real providers

Set `MARA_CASE_CHAT_API_KEY` and `MARA_CASE_EMBEDDING_API_KEY` in the process
environment. Harbor uses a Deepseek chat key and an OpenAI embedding key. Chart
uses an OpenAI chat key for `gpt-4.1-mini-2025-04-14` and an OpenAI embedding key
for `text-embedding-3-large`. Configure network/proxy settings for your host if
needed. Do not put credentials into the distributed files.

```shell
python review_followup/run_followup.py --case harbor --source /path/to/LMDoc-case-source --output /path/to/new-empty-harbor-directory
python review_followup/run_followup.py --case chart --source /path/to/LMDoc-case-source --output /path/to/new-empty-chart-directory
```

The script forces an isolated package-settings module, indexes the provided
documents with actual embeddings, and calls real providers. It refuses a
nonempty output directory. Provider behavior can change; Harbor uses a model
alias. A route timeout is cooperative on Windows and is not a hard process kill.
The distributed chart script was executed in another empty runtime; it repeats
the -50% text/auto, -40% visual, and -50% image-removed observations. All of that
run is included in `recipe_validation/`; it is repetition of the same task.
Private runtime databases can persist keys: share only checked, redacted records,
never a new run's `runtime/` directory.

The chart recipe replays the final adapted question through fixed text, auto,
and manually selected visual routes. `--question` can rerun the longer original
question from `preliminary-slot-failure/protocol.json`. That original question
failed required-slot adequacy before generation. The final question and manual
intervention were chosen after observing those failures; this is a constructed
diagnostic walkthrough, not a prespecified benchmark sample. The initial setup
failure is in `setup-failure.json`.

Image data URLs in recorded visual requests are externalized without loss:
`relative_file` identifies the exact bytes, `sha256` checks them, and `encoding`
preserves the data-URL prefix. Base64-encode those bytes and prepend that prefix
plus a comma to reconstruct the transmitted value. The image-removed control
retains every other request field. The adapter name `local_qwen3_vl` is a legacy
registry label; actual requested and returned model names are captured.

## Scope and verification

The six focused regression cases include wrong numbers, negations, and absent
support. The verifier/controller suite passes 129 tests. Other pre-commit hooks
pass. The Windows mypy hook has eight existing POSIX-attribute errors in untouched
modules; its environment passes the changed files with Linux platform assumptions.
Logs are included. No release-wide or general reliability claim follows.

The old video, original case, and historical benchmark archive are unchanged.
There is no participant study, timed comparison with Kotaemon, automatic recovery
demonstration, or recovered historical SlideVQA generation trace in this addition.
