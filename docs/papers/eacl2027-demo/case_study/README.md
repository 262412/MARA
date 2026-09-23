# A recorded diagnosis: successful retrieval, refused answer

Open **walkthrough.html** for the complete sequence. No server, API key, or
installation is required to view it. This is a presentation of captured runtime
records, not a screenshot of an additional native MARA interface.

The fictional Harbor pilot has two documents. The operating guide points to the
data policy, and the latter says to retain raw sensor logs for 17 days. A user
initially selects only the operating guide and cannot complete the question.
The visible refusal mentions retrieval, but the structured response reports
successful text retrieval and a completed provider call. Strict verification is
unknown and the guardrail abstains. Inspection of the retrieved text reveals the
missing policy. Selecting that policy, with all other request fields unchanged,
produces a cited 17-day answer with supported verification and a return decision.

This demonstrates a user-directed source correction. Neither turn switches route,
uses a VLM, or establishes general accuracy or usability improvements. The first
refusal is reasonable for the selected source; its generic wording does not
correctly identify the blocking stage. We retain that limitation.

## Offline verification

With any Python 3.10+ installation, run:

```shell
python verify_case.py
```

The standard-library verifier checks the SHA-256 manifest, source text in captured
prompts and evidence, preserved raw/intermediate/displayed answers, decision
outcomes, identical effective settings, and the sole request change. It recomputes
the stored EM/token-F1 checks from the displayed answer against the stated
reference. The scoring projection is identity. Normalization removes numbered
`【n】` citations, ASCII punctuation, English articles, case, and excess whitespace.
This is a fixture check, not a benchmark estimate or a claim that source correction
raises population F1. All originals in `records/` remain readable without Python.

## New execution with real providers

Install the reviewer package from the paper's release link. Use its Python at
`runtime/environment/Scripts/python.exe`. Set `MARA_CASE_CHAT_API_KEY` and
`MARA_CASE_EMBEDDING_API_KEY` in your process environment for the configured
Deepseek and OpenAI providers. An appropriate `HTTPS_PROXY` may be needed in your
network; no proxy endpoint is hard-coded in the reproduction script.

```shell
python run_case.py --output PATH_TO_NEW_EMPTY_DIRECTORY
```

This indexes the two supplied files and calls the actual providers. It does not
replay stored answers. It uses an isolated application home and refuses to
overwrite nonempty output directories. Do not point it at your normal app data.
The unused reranker entry only satisfies this build's configuration requirement;
reranking is disabled. Credentials may be persisted by MARA in the private runtime
database, so share only redacted records, never that directory or database.

The main frozen record is the first successfully completed pair of turns. We also
tested this script in a second empty runtime; all results are retained in `repeat/`.
That run abstained for the operating guide again. With the correct policy selected,
the model generated the 17-day fact plus extra explanation; strict verification
supported the core fact but rejected an extension, so the final response abstained.
This negative repetition is part of the evidence, not discarded. It shows why the
successful first pair cannot establish stable recovery. The provider model name is
an alias, and generation and heuristic verification are not deterministic. An
offline audit of recorded outputs is distinct from a live rerun.

## Evidence map

- `case-protocol.json`: question, reference source, intervention and capture scope.
- `records/*-request.json`: full request snapshots, including intended settings.
- `records/*-response.json`: full structured responses and effective settings.
- `records/*-provider-calls.json`: observed text-provider inputs and output chunks.
- `records/answer-stages.json`: raw, pre-verification, pre-guardrail, displayed and
  scoring answers kept separately. Historical benchmark adapters are not applied.
- `records/*-cli-rendered.txt`: responses rendered using MARA's existing CLI
  formatter; these are derived displays, not a second execution.
- `records/effective-config.json`: redacted providers, package versions, observed
  generation method and explicit fields the runtime did not report.
- `records/source-verification.json`: installed/source hash matches for inspected
  runtime files; the installer commit is `e6afa5dc`.
- `upstream/`: licensed source snapshots and the static Kotaemon comparison.

The old synthesis ZIP remains unchanged. Its missing raw outputs, effective job
configs, and actual per-answer generation paths are not recovered by this case.
In particular, the precise historical cause of SlideVQA's ties remains unresolved.
The original demonstration video is unchanged.

Here, raw provider text means concatenated answer-content chunks exposed by the
runtime adapter, before MARA's answer processing. It is not a full HTTP response,
hidden reasoning trace, or a record of the provider's internal model state.

## License

The fictional source documents, case scripts and explanatory materials are
released under Apache-2.0 with MARA. The upstream source snapshot retains
Kotaemon's Apache-2.0 license. No private documents or API keys are distributed.
