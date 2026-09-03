# QASPER semantic proposition debug trace

The semantic debug trace is a default-off diagnostic surface for following one
typed proposition across model proposal, entailment audit, authority binding,
QueryPlan slots, recovery, and terminal publication. Enabling it does not alter
retrieval, verification, authority, recovery, scoring, or abstention decisions.

Set `MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE=1` for a benchmark process. Slurm
debug runs can additionally set `MARA_REQUIRE_SEMANTIC_DEBUG_TRACE=1`; the text
runner then fails closed unless it publishes one row per prediction.

The formal full-system QASPER launcher sets both variables. Required projection
then emits exactly one structured transaction row per prediction, including
predictions that fail before candidate generation or verification. Such a row
preserves the transaction's real `incomplete` status when stages are missing;
the publisher compares ordered `(example_id, route)` identities and the
12-stage digest/chain shape, and continues to fail closed on any mismatch.

The runtime contracts are:

- `semantic_proposition_debug_trace.v1`: ordered model transactions and cache
  reuse, including packed canonical evidence, required slots, bounded raw model
  responses, parsed values, retry failures, audit outcomes, and whether proposal
  and audit used the same model instance.
- `semantic_proposition_authority_debug.v1`: ordered header, premise, and
  derivation validation stages for each authority attempt.
- `qasper_semantic_pipeline_debug.v1`: benchmark projection that joins semantic
  transactions, authority stages, controller recovery events, final required
  slot states, typed authority, and terminal outcome.

Debug history is bounded to 16 semantic events and 16 authority attempts per
route execution. Each raw model response is bounded to 16,000 characters and
records whether truncation occurred. Normal runs do not retain raw model output.

When at least one prediction contains a debug trace, `benchmark.reports` writes
`semantic_debug_traces.jsonl`, includes its digest and physical line count in
the normal artifact manifest, and adds aggregate finding counts to
`summary.json`. Findings are diagnostic; they never change answer acceptance.

Build an exact schema-v2 subset without embedding benchmark IDs in runtime
logic:

```bash
python scripts/slurm/build_manifest_subset.py \
  --source /path/to/source-manifest.json \
  --output /path/to/debug-manifest.json \
  --example-id EXAMPLE_ID
```

Repeat `--example-id` for a small cohort. The builder preserves the requested
example order and original routes, retains only referenced documents, and fails
closed on missing or duplicate identities.
