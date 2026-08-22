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
- [ProofWriter](https://aclanthology.org/2021.findings-acl.317/) distinguishes
  an open-world unknown from a proved false proposition and emits inspectable
  proofs.

MARA does not import code or model weights from these projects. Their evidence
set, explicit-premise, and open-world semantics inform this local contract.

## Runtime shape

The existing `typed_proposition_authority.v1` envelope remains the public
authority projection. Composite support adds:

- `authority_derivations`: verified proof alternatives;
- `selected_derivation_id`: the one proof used for the terminal decision;
- `authority_atoms`: every exact evidence-span leaf in the selected proof;
- `slot_bindings`: every evidence identity required by those leaves.

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
- `qasper_composite_authority_count`;
- `qasper_composite_authority_invalid_count`.

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
