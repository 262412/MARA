# Same task, pinned upstream inspection

Upstream: Cinnamon/kotaemon, commit
`9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9`.
Method: static source walkthrough. No upstream UI, live provider comparison,
user timing, click count, or head-to-head answer-quality experiment was run.

The included `inspected-source.zip` contains the exact files below with
`LICENSE.txt`. Their hashes appear in `provenance.json`.

| Task | Upstream capability and source | Additional DocQA-Inspect evidence in this case |
| --- | --- | --- |
| Check selected source | `libs/ktem/ktem/index/file/ui.py`, `File.file_selected` and file selector controls; chat supports file tags | `selected_file_ids` plus source name/text in `evidence_bundle.items` |
| Inspect why the question was unresolved | `libs/ktem/ktem/reasoning/simple.py`, `show_citations_and_addons`, exposes evidence and optional low-context-relevance warnings | Separate `route_decision`, `retrieve_decision`, `verify_decision`, `guardrail_decision`; a good retrieval can coexist with verification abstention |
| Correct the source | File selection and another question already exist upstream | Same user operation; compare the exported requests to check that only the source changed |
| Preserve the interaction | `libs/ktem/ktem/pages/chat/__init__.py`, `persist_data_source` (lines 1091–1159) retains selected sources, messages, retrieval messages, plots and state | The public DocQA structured response also retains stage decisions and evidence; the supplementary observer additionally captures provider outputs |

Inspecting the upstream paths did not find DocQA-Inspect's explicit decision-field schema.
This supports the narrow export/inspection distinction. It does not mean upstream
cannot be debugged, that it has no traces or graph features, or that source
reselection is new. Provider-output capture in this package is a supplementary
observer, not a claim that the native UI previously exported every such field.

Permanent source links:

- [Conversation persistence](https://github.com/Cinnamon/kotaemon/blob/9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9/libs/ktem/ktem/pages/chat/__init__.py)
- [Evidence display](https://github.com/Cinnamon/kotaemon/blob/9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9/libs/ktem/ktem/reasoning/simple.py)
- [File selection](https://github.com/Cinnamon/kotaemon/blob/9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9/libs/ktem/ktem/index/file/ui.py)
