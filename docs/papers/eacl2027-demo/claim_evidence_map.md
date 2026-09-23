# Claim and evidence map

| Claim | Evidence | Status | Boundary |
| --- | --- | --- | --- |
| Historical automatic routing does not consistently improve answer F1 | Unchanged synthesis ZIP and audit/revision-evidence.json | retained and recomputed | No new benchmark observations |
| The case's initial refusal occurs after good retrieval and completed generation | case_study/records/before-response.json and before-provider-calls.json | observed | Constructed source-scope task |
| Changing only the selected source yields a supported 17-day answer in the captured pair | Both request/response records and verify_case.py | observed and verified | Single pair, no general recovery claim |
| A fresh repetition can still abstain with the correct source | case_study/repeat/after-response.json and provider-calls | observed and retained | Strict verifier rejects extra explanation |
| The raw-to-displayed answer transition can be inspected for this case | records/answer-stages.json and complete provider outputs | observed and checked | Does not recover missing historical answers |
| Upstream already supports source selection, evidence viewing and persistence | Pinned upstream source ZIP and COMPARISON.md | static inspection | No executed upstream comparison or timing claim |
| MARA adds explicit stage decisions to this diagnosis | Public response fields, runtime source hashes and case records | observed | Provider-output observer is supplementary instrumentation |
| Existing video covers a text user workflow | Unchanged video and manuscript disclosure | retained scope | No new video scenes, route-switch or VLM demonstration |
