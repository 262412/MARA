from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any, cast

from ktem.docqa.boolean_evidence_scope import evidence_item_text
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning.mara_qasper_candidate import (
    _record_candidate_request,
    _record_candidate_response,
)
from ktem.reasoning.mara_qasper_candidate_prompt import _candidate_evidence
from ktem.reasoning.mara_qasper_candidate_request import fit_candidate_request
from ktem.reasoning.mara_qasper_candidate_transport import (
    qasper_candidate_response_format,
)
from ktem.reasoning.mara_semantic_candidate_policy import candidate_bound_response

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.tests.qasper_terminal_projection_fixture import (
    attach_valid_terminal_projection,
)
from scripts.slurm import qasper_natural_semantic_pack_probe as probe
from scripts.slurm.qasper_natural_production_path_probe import (
    _record_production_verifier_trace,
    _run_semantic_transaction,
)
from scripts.slurm.qasper_natural_semantic_pack_replay import candidate_replay_context

CODE_SHA = "a" * 40


def row() -> dict[str, object]:
    question = "Did they inspect image parts?"
    text = "They inspected image regions."
    return attach_valid_terminal_projection(
        attach_replay_context(
            {
                "example_id": "natural-probe-example",
                "route": "text_rag",
                "question": question,
                "gold_answers": ["yes"],
                "evidence_bundle": {
                    "items": [
                        {
                            "evidence_id": "natural-probe-evidence",
                            "source_id": "paper",
                            "text": text,
                        }
                    ]
                },
                "evidence_metadata": {
                    "query_plan": {
                        "evidence_slots": [
                            {
                                "slot_id": "support:boolean_proposition",
                                "description": "complete proposition support",
                                "required_for_verification": True,
                                "evidence_ids": [],
                                "evidence_refs": [],
                            }
                        ]
                    }
                },
                "qasper_annotation_diagnostics": {
                    "ambiguity_reasons": [],
                    "boolean_no_evidence_semantics": {},
                },
            }
        )
    )


def attach_replay_context(row: dict[str, Any]) -> dict[str, Any]:
    bundle = cast(dict[str, Any], row["evidence_bundle"])
    items = cast(list[dict[str, Any]], bundle["items"])
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    query_plan = cast(dict[str, Any], metadata["query_plan"])
    source_items = []
    ranked = []
    for index, item in enumerate(items, start=1):
        text = evidence_item_text(item)
        evidence_id = identity_of(item).key
        source_items.append(
            {
                "source_item_index": index,
                "evidence_id": evidence_id,
                "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_chars": len(text),
                "identity_decision": "eligible",
                "identity_reason": "accepted_for_semantic_ranking",
            }
        )
        ranked.append({"ranked_position": index - 1, "canonical_id": evidence_id})
    snapshot = {
        "contract_id": "semantic_source_input_snapshot.v1",
        "complete": True,
        "source_items": source_items,
        "ranked_evidence_present": True,
        "ranked_evidence": ranked,
        "query_plan": deepcopy(query_plan),
        "query_plan_digest": canonical_digest(query_plan),
        "max_context_length": None,
    }
    snapshot["snapshot_digest"] = canonical_digest(snapshot)
    metadata["qasper_canonical_semantic_pack"] = {
        "source_packing_observation": {"source_input_snapshot": snapshot}
    }
    transaction_id = "c" * 64
    metadata["qasper_candidate_generation"] = {
        "trace_group_id": "natural-probe-fixture",
        "benchmark_route_id": str(row.get("route") or ""),
        "internal_route": str(row.get("route") or ""),
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:candidate_generation:1",
        "generation_sequence": 0,
        "predecessor_transaction_id": "",
        "effective_seed": 20260724,
        "candidate_request_dropped_evidence_count": 0,
    }
    row["retrieved_hits"] = deepcopy(items)
    record_fixture_candidate_request(row)
    replay = candidate_replay_context(row)
    context = probe.freeze_natural_pack(
        str(row.get("question") or ""),
        route=str(row.get("route") or ""),
        example_id=str(row.get("example_id") or ""),
        replay=replay,
        code_sha=CODE_SHA,
    )
    metadata["qasper_candidate_generation"] = deepcopy(context.candidate_generation)
    metadata["qasper_candidate_generation"]["model"] = "fixture-candidate-model"
    metadata["qasper_canonical_semantic_pack"] = deepcopy(
        context.bundle.metadata["qasper_canonical_semantic_pack"]
    )
    metadata["candidate_ranked_evidence"] = deepcopy(
        context.bundle.metadata["candidate_ranked_evidence"]
    )
    metadata["semantic_proposition_verifier"] = fixture_semantic_trace(
        context,
        question=str(row.get("question") or ""),
    )
    return row


def fixture_semantic_trace(context: Any, *, question: str) -> dict[str, Any]:
    binding = cast(
        dict[str, Any],
        context.bundle.metadata["qasper_canonical_semantic_pack"][
            "proposition_binding"
        ],
    )
    if binding.get("binding_state") != "relation_bound_support":
        return fixture_not_run_verifier(context)
    plan = cast(
        dict[str, Any],
        binding["canonical_evidence_plan"]["support_plan"],
    )
    proposal = fixture_proposal(plan)
    audit = fixture_audit(plan)
    outcome = _run_semantic_transaction(
        context,
        context.bundle,
        deepcopy(context.bundle.metadata),
        question=question,
        candidate="yes",
        candidate_generation=context.candidate_generation,
        source_metadata=context.bundle.metadata,
        raw_proposal=proposal,
        raw_audit=audit,
    )
    assert outcome.status == "parsed"
    return fixture_verifier_trace(context, outcome, question=question)


def fixture_proposal(plan: dict[str, Any]) -> str:
    return json.dumps(
        {
            "candidate_judgment": "supported",
            "canonical_evidence_plan_id": plan["plan_id"],
        }
    )


def fixture_audit(plan: dict[str, Any]) -> str:
    premise_checks: dict[str, Any] = {}
    for index, span_ref in enumerate(plan.get("span_refs") or [], start=1):
        slots = [
            slot
            for slot, refs in (plan.get("slot_refs") or {}).items()
            if span_ref in refs
        ]
        premise_checks[f"P{index}"] = {
            "fragment_entailed": True,
            "scope_consistent": True,
            "evidence_relation_valid": True,
            "proposition_slot_checks": {
                slot: {
                    "binding_valid": True,
                    "evidence_ref": f"P{index}:{slot}",
                }
                for slot in slots
            },
        }
    return json.dumps(
        {
            "premise_checks": premise_checks,
            "jointly_entails": True,
            "each_premise_required": True,
            "contradiction_free": True,
            "conclusion_check": {
                "conclusion_entailed": True,
                "actor_consistent": True,
                "predicate_consistent": True,
                "object_consistent": True,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
        }
    )


def fixture_verifier_trace(
    context: Any,
    outcome: Any,
    *,
    question: str,
) -> dict[str, Any]:
    runtime_metadata: dict[str, Any] = {}
    _record_production_verifier_trace(
        runtime_metadata,
        context=context,
        outcome=outcome,
        response=candidate_bound_response(outcome.value, "yes"),
    )
    trace = runtime_metadata["semantic_proposition_verifier"]
    diagnostics = cast(dict[str, Any], outcome.diagnostics)
    transaction = deepcopy(outcome.debug_trace or {})
    trace["debug_trace"] = {
        "contract_id": "semantic_proposition_debug_trace.v3",
        "event_count": 1,
        "dropped_event_count": 0,
        "events": [
            {
                "event": "model_transaction",
                "cache_key": "fixture-natural-semantic-pack",
                "question": question,
                "required_slots": deepcopy(context.slots),
                "packed_evidence": deepcopy(context.frozen.records),
                "auditor_relationship": str(
                    transaction.get("auditor_relationship")
                    or diagnostics.get("auditor_relationship")
                    or ""
                ),
                "outcome": {
                    "status": str(outcome.status or ""),
                    "reason": str(outcome.reason or ""),
                    "verdict": str((outcome.value or {}).get("verdict") or ""),
                    "audit_status": str(diagnostics.get("audit_status") or ""),
                    "audit_reason": str(diagnostics.get("audit_reason") or ""),
                    "proof_mode": str(diagnostics.get("proof_mode") or ""),
                    "typed_conclusion": deepcopy(
                        diagnostics.get("typed_conclusion") or {}
                    ),
                    "conclusion_audit": deepcopy(
                        diagnostics.get("conclusion_audit") or {}
                    ),
                    "recovery_transitions": deepcopy(
                        diagnostics.get("recovery_transitions") or []
                    ),
                },
                "transaction": transaction,
            }
        ],
    }
    return trace


def fixture_not_run_verifier(context: Any) -> dict[str, Any]:
    return {
        "contract_id": "semantic_proposition_verifier_runtime.v3",
        "status": "not_run_after_candidate_response_replay",
        "reason": "stage_nine_not_replayed",
        "candidate_verification_status": "not_started_in_replay",
        "proposal_status": "not_started",
        "audit_status": "not_started",
        "semantic_data_lineage": {
            "contract_id": "semantic_proposition_data_lineage.v1",
            "source_packing": deepcopy(
                context.bundle.metadata["qasper_canonical_semantic_pack"][
                    "source_packing_observation"
                ]
            ),
            "plan_construction": deepcopy(context.binding["plan_construction_trace"]),
        },
    }


def record_fixture_candidate_request(row: dict[str, Any]) -> None:
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    initial = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    replay = candidate_replay_context(row)
    question = str(row["question"])
    transaction_id = str(initial["transaction_id"])
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="qasper",
        dataset_family="qasper",
        answer_type="boolean",
        question=question,
        query=question,
        query_plan=deepcopy(replay.query_plan),
    )
    bundle = EvidenceBundle(
        route=str(row["route"]),
        items=deepcopy(replay.items),
        metadata=deepcopy(replay.bundle_metadata),
    )
    records, diagnostics, _source_packing = _candidate_evidence(
        request,
        question,
        bundle,
        candidate_transaction_id=transaction_id,
    )
    response_schema = qasper_candidate_response_format()
    (
        records,
        diagnostics,
        messages,
        token_measurement,
        dropped_count,
    ) = fit_candidate_request(
        None,
        question,
        records,
        diagnostics,
        response_schema=response_schema,
        controlled_candidate="",
        candidate_transaction_id=transaction_id,
    )
    identity = {
        key: deepcopy(initial.get(key))
        for key in (
            "trace_group_id",
            "benchmark_route_id",
            "internal_route",
            "transaction_id",
            "attempt_id",
            "generation_sequence",
            "predecessor_transaction_id",
        )
    }
    observation, _input_digest = _record_candidate_request(
        bundle,
        llm=None,
        messages=messages,
        response_schema=response_schema,
        identity=identity,
        route=str(row["route"]),
        seed=int(initial["effective_seed"]),
        evidence=records,
        evidence_diagnostics=diagnostics,
        controlled_candidate="",
        token_measurement=token_measurement,
        request_dropped_count=dropped_count,
    )
    record_fixture_candidate_response(observation, identity)
    metadata["qasper_candidate_generation"] = observation


def record_fixture_candidate_response(
    observation: dict[str, Any],
    identity: dict[str, Any],
) -> None:
    _record_candidate_response(
        SimpleNamespace(
            text='{\n\n\n    "candidate": "yes"\n}',
            completion_tokens=10,
            prompt_tokens=observation["estimated_input_tokens"],
            finish_reason="stop",
        ),
        observation,
        identity,
        str(observation["input_digest"]),
        "",
    )
