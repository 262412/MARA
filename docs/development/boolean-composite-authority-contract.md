# Boolean Composite Authority Contract

## Purpose

Some Boolean propositions are not asserted by one evidence span. A complete
proposition can instead require several exact spans, such as two empirical
sentences that cover different required arguments, or an entity-type
declaration joined to an empirical statement about that entity.

The composite-authority path makes that reasoning explicit. It is a DocQA
verification capability; QASPER is one consumer and is not part of the core
rule definitions.

## Research basis

The design follows four established ideas:

- [FEVER](https://aclanthology.org/N18-1074/) records the sentence or sentences
  necessary for a supported or refuted judgment.
- [FEVEROUS](https://fever.ai/2021/task.html) permits sentence, table-cell,
  caption, and list evidence that may establish the label only when examined
  together.
- [EntailmentBank](https://aclanthology.org/2021.emnlp-main.585/) represents
  explanations as multi-premise entailment steps from facts to a hypothesis.
- [FActScore](https://aclanthology.org/2023.emnlp-main.741/) separates atomic
  claim construction from checking each claim against a reliable source.
- [MiniCheck](https://arxiv.org/abs/2404.10774) treats grounded fact checking as
  an independent claim-versus-document decision and explicitly covers claims
  that require synthesis across several sentences.
- [ProofWriter](https://aclanthology.org/2021.findings-acl.317/) distinguishes
  an open-world unknown from a proved false proposition and emits inspectable
  proofs.
- [QASPER](https://aclanthology.org/2021.naacl-main.365/) requires evidence
  that may be spread across multiple paper sections, tables, and figures. Its
  official evaluator keeps each annotation's answer-and-evidence set as a
  separate reference rather than flattening all annotators into one proof.

MARA does not import code or model weights from these projects. Their evidence
set, explicit-premise, and open-world semantics inform this local contract.

## Runtime shape

The existing `typed_proposition_authority.v1` envelope remains the public
authority projection. Composite support adds:

- `authority_derivations`: verified proof alternatives;
- `selected_derivation_id`: the one proof used for the terminal decision;
- `authority_atoms`: every exact evidence-span leaf in the selected proof;
- `slot_bindings`: every canonical evidence identity required by those leaves;
- `slot_ref_bindings`: optional exact span references for rules where two
  premises can occupy the same canonical evidence item.

Each `boolean_authority_derivation.v1` record contains:

- a deterministic `derivation_id` over its semantic content;
- a registered `rule_id`;
- `premise_mode=all_required` and `semantics=open_world`;
- exact `premise_refs` and aligned `premise_evidence_ids`;
- per-premise contributions;
- a complete typed conclusion;
- required and covered argument tokens;
- explicit entity bindings when a rule performs a typed join.

The typed transaction is mandatory for QASPER. Outside QASPER it is also
committed whenever the general verifier produces an explicit composite Boolean
proof, so the capability is not tied to a benchmark adapter.

Within one derivation the premises are an AND set. Multiple derivations are
alternative proofs, but the current runtime commits exactly one minimal proof.
This avoids mixing leaves from different alternatives.

## Initial rules

### Same-source argument conjunction

`same_source_argument_conjunction.v1` combines non-overlapping, exact,
assertive spans when every span contributes a proper subset of the required
arguments and their union exactly covers the proposition.

The rule is intentionally inapplicable to:

- disjunctions;
- comparisons or ordered relations;
- existential, same-event, or single-event binding requirements;
- coordinated predicates;
- future-work, related-work, unsafe-scope, or negative premises;
- implicit joins across source identities.

### Same-source entity-type join

`same_source_entity_type_join.v1` joins an explicit named-entity type
declaration to an empirical relation involving that exact entity. Both spans
remain proof leaves and both must be cited. The former hidden projection that
treated only the empirical sentence as complete authority is not used.

### Grounded semantic evidence-set entailment

`grounded_semantic_evidence_set_entailment.v3` handles propositions whose
premise relationship is semantic rather than a registered lexical join. It
separates two proof modes instead of treating every semantic proof as a
conjunction:

- `atomic_semantic` contains exactly one premise that entails the complete
  typed conclusion;
- `composite_conjunction` contains two to four non-overlapping premises that
  are all necessary and jointly entail the complete typed conclusion.

A conservative proposition proposer selects canonical runtime-provided spans
from one source and returns:

- one `yes`, `no`, or `insufficient_evidence` verdict under
  `semantic_proposition_verdict.v3`;
- `support_mode=evidence_set`;
- the explicit proof mode;
- an all-premises-required attestation;
- a distinct proposition fragment for every quote;
- the exact QueryPlan verification slots supported by every premise; and
- a model, seed, and verifier contract attestation.

The runtime first creates a `question_proposition.v1` value containing the
complete question surface plus its actor, predicate, argument surfaces, scope,
qualifier, quantifier, modality, negation, and time fields. A proposed polarity
creates a digest-bound `typed_conclusion.v1`. The first model response is only a
proof proposal, never authority.

Before typed commit, a separate `semantic_entailment_audit.v2` transaction
receives the typed question, typed conclusion, proof mode, exact quotes, and
proposition fragments. It checks every premise independently and checks the
complete conclusion's polarity, quantifier, and scope. The resulting
`conclusion_audit.v1` is bound to the exact conclusion digest. Release-mode
QASPER execution fails before the proposer call if proposer and auditor are the
same model instance; a separate instance of the same model or a distinct model
still performs a separate request, parse, and attestation.

The local parser performs deterministic cross-field checks in addition to the
provider schema. In particular, `jointly_entails=true` cannot coexist with a
false premise check. Such a response enters bounded `proof_repair`: the runtime
may prune rejected premises only if the remaining proof still covers every
required slot, otherwise it asks the proposer to rebuild from the canonical
selectors. Either path discards the old audit and runs the complete independent
audit again. A second contradictory audit is not repaired recursively.

An accepted audit records per-premise quote and fragment digests plus a digest
of the complete proposed transaction. The audit is included in the verifier
attestation and therefore in the deterministic derivation identity. Runtime and
benchmark validators recompute the proposal digest from the typed atoms and
premise contributions. Re-identifying a derivation after changing a fragment,
quote, slot binding, polarity, or audit cannot make it valid.

Before either model call, runtime deterministically segments the packed text
into bounded canonical sentence/spans. The proposer returns selector IDs, not
free-form quotes; the local parser materializes each exact quote and its local
and canonical offsets. The provider schema deliberately keeps the selector as
a bounded string rather than embedding a potentially large dynamic enum; exact
selector membership is enforced locally. After audit, runtime resolves every
evidence identity back to one canonical item and rechecks quote bytes, offsets,
source identity, overlap, scope, slot coverage, audit binding, and derivation
identity before creating typed atoms. An audit rejection is a normal fail-closed
`insufficient_evidence` outcome. A missing, malformed, or provider-failed audit
is a verifier failure and cannot publish authority.

Scope is validated at two levels. A local definition or component description
may be a valid premise even when it does not independently establish the whole
paper-level claim. The complete premise set must still establish either an
explicit current-author action, an explicit prior-work actor for a prior-work
question, or a named question subject grounded in the selected quotes. This
prevents a useful local definition from being discarded while still blocking
two generic descriptions from being promoted into an invented author action.

`No` remains stricter than `Yes`: the selected evidence set must contain a
deterministically resolvable negative or contradictory target relation.
Missing retrieval, an empty evidence annotation, or a model's unsupported
negative judgment cannot establish negative authority.

The verifier runs only after deterministic Boolean verification remains
unknown. It receives the typed question, required QueryPlan slots, and bounded
canonical evidence spans, but not the generated answer. Calls use a stable seed
and strict JSON schema. The route-local cache is keyed by a semantic-pack digest
over the typed proposition, complete slot descriptions, actual ordered prompt
spans and offsets, stable evidence provenance, packing limits, system prompt,
and contract versions. Runtime UUID churn is deliberately absent from this
digest.

The provider-facing schema stays within the backend's supported grammar subset;
set uniqueness is enforced again by the strict local parser instead of relying
on `uniqueItems`. Prompt packing preserves complete canonical excerpts first,
prioritizes QueryPlan-bound evidence and then the upstream reranker order, and
only uses a question-relevant partial window when a lower-priority full excerpt
cannot fit. A conservative estimate caps the complete system-plus-user input at
3072 tokens and the proposal response at 768 tokens for a 4096-token minimum
context. This leaves a 256-token context reserve while accommodating a complete
four-premise JSON proof. A parse failure receives one bounded corrective retry.
If it still fails, runtime records whether the provider exhausted its output
budget or the local cross-field parser rejected the object; response text is not
persisted. The audit prompt is bounded separately and has a 512-token output
cap.

Recovery is recorded as one of `proof_repair`, `quote_rebind`, or
`evidence_retrieval`. Controller recovery records both raw-evidence and
semantic-pack digests before and after the transition. A fresh semantic model
verification is allowed only when the semantic-pack digest changes; changes to
runtime IDs, unselected text, or other non-prompt state cannot create a new
verification attempt. Proof repair remains an internal audited transaction and
always performs its required full re-audit.

## Fail-closed invariants

A composite proposition is verified only when all of the following hold:

1. The rule, contract, open-world semantics, and all-required operator match.
2. Every premise has a unique exact quote reference and a canonical evidence
   identity.
3. Every premise quote is independently grounded at its recorded offsets.
4. Premises have the same source identity and do not overlap.
5. Contribution records match the evidence identities and are recomputed from
   the quoted text.
6. No proper subset of an argument-conjunction proof covers the conclusion.
7. The conclusion frame, polarity, relation, quantifier, and argument set are
   complete.
8. The deterministic derivation identity recomputes exactly.
9. QueryPlan's `boolean_support_group` matches the selected derivation.
10. QueryPlan slots, verified claim support, verified citations, and typed
    authority bind every selected premise.
11. Semantic proofs bind premise contributions into the derivation identity
    and preserve exact span-level slot references.
12. Semantic scope is complete at the proposition level, and negative
    authority contains an explicit target-relation contradiction.
13. Every semantic premise fragment and the joint conclusion have a verified,
    proposal-bound independent entailment audit.
14. Proof-mode cardinality is exact: one premise for `atomic_semantic`, and two
    to four all-required premises for `composite_conjunction`.
15. The typed question, typed conclusion, conclusion audit, auditor
    relationship, and semantic-pack digest remain bound through commit.
16. A repaired proof has a complete fresh audit; recovery cannot reverify an
    unchanged semantic pack.

If any invariant fails, the transaction is downgraded coherently to missing
authority and the answer remains unknown or abstained. Missing evidence never
implies a negative answer.

## Single-span compatibility

An independently complete exact span still wins over a composite proof. Its
existing scalar authority fields remain unchanged. For a composite proof,
those scalar fields are empty; consumers must use the typed conclusion and
derivation rather than pretending the first premise proves the whole claim.

## Benchmark alignment

The QASPER runtime audit independently validates the selected derivation,
premise atoms, QueryPlan operator, slot bindings, and required citations. It
emits:

- `runtime_typed_authority_kind`;
- `runtime_typed_authority_derivation_status`;
- `runtime_typed_authority_derivation_count`;
- `runtime_typed_authority_selected_derivation_id`;
- `runtime_typed_authority_premise_refs`;
- `runtime_typed_authority_premise_evidence_ids`;
- `runtime_typed_authority_slot_ref_bindings`;
- `runtime_semantic_proposition_authority_status` and its reason;
- `runtime_semantic_proposition_verifier_status`, model-call count, evidence
  packing count, per-item character limit, conservative input-token estimate and
  budget, dropped/truncated evidence counts, prompt/output bounds, cache status,
  verdict, retry count, parse reason, finish reason, response token count, and
  response size;
- `runtime_semantic_entailment_audit_status`, reason, model, call/retry counts,
  response diagnostics, contract, and proposal digest;
- `runtime_semantic_proof_mode`, `runtime_semantic_question_proposition`, and
  `runtime_semantic_typed_conclusion`;
- `runtime_semantic_auditor_relationship` and
  `runtime_semantic_conclusion_audit`;
- `runtime_semantic_pack_digest`, cache source and source-event index;
- `runtime_semantic_recovery_transitions` and the latest typed recovery
  transition;
- `qasper_composite_authority_count`;
- `qasper_composite_authority_invalid_count`;
- `qasper_semantic_evidence_set_authority_count`;
- `qasper_semantic_evidence_set_authority_invalid_count`;
- `qasper_semantic_proposition_verifier_call_count`;
- `qasper_semantic_proposition_verifier_failure_count`;
- `qasper_semantic_proposition_verifier_context_overflow_count`;
- `qasper_semantic_proposition_verifier_schema_unsupported_count`;
- `qasper_semantic_proposition_output_truncation_count`;
- `qasper_semantic_proposition_json_decode_failure_count`;
- `qasper_semantic_proposition_parse_contract_rejection_count`;
- `qasper_semantic_entailment_audit_call_count`;
- `qasper_semantic_entailment_audit_failure_count`;
- `qasper_semantic_entailment_audit_rejection_count`.

The converter also preserves QASPER figures/tables and emits
`qasper_reference_sets.v1`, including annotation identity, answer type,
per-annotation evidence, highlighted evidence, and support mode. Native answer
and evidence scoring consumes these reference sets first and retains the legacy
union only as a compatibility fallback. These benchmark fields audit the
runtime contract; they do not manufacture authority or answers.

All selected proof leaves are necessary citations. Therefore citation
minimality uses the number of distinct required evidence identities, rather
than assuming every Boolean answer has exactly one citation.
Legacy single-authority quote fields remain empty for a composite proof, so a
consumer cannot accidentally collapse the proof to its first premise.

## Extension protocol

New rules must be generic proposition rules, not example identifiers or gold
answer mappings. An extension must provide a deterministic producer, an
independent validator branch, QueryPlan projection, negative tests, tamper
tests, and benchmark audit coverage. A rule that needs event identity,
cross-document entity resolution, temporal ordering, or comparison operands
must model that binding explicitly before it may publish a conclusion.
