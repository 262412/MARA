from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning.mara_qasper_candidate import (
    _record_candidate_request,
    _serialized_messages,
)
from ktem.reasoning.mara_qasper_candidate_evidence import candidate_evidence_set_binding
from ktem.reasoning.mara_qasper_candidate_prompt import (
    _bound_candidate_slots,
    _candidate_evidence,
)
from ktem.reasoning.mara_qasper_candidate_request import (
    candidate_messages,
    candidate_request_diagnostics,
)
from ktem.reasoning.mara_qasper_candidate_transport import (
    qasper_candidate_response_format,
)
from ktem.reasoning.mara_qasper_semantic_pack import (
    freeze_qasper_canonical_semantic_pack,
    load_qasper_canonical_semantic_pack,
)
from ktem.reasoning.mara_qasper_semantic_pack_observation import (
    qasper_candidate_pack_identity_projection,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    required_semantic_proposition_slots,
)

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from scripts.slurm.qasper_natural_candidate_response_replay import (
    replay_frozen_candidate_response,
)
from scripts.slurm.qasper_natural_semantic_pack_replay import CandidateReplayContext


@dataclass(frozen=True)
class NaturalPackContext:
    bundle: EvidenceBundle
    slots: list[dict[str, Any]]
    frozen: Any
    loaded: Any
    load_reason: str
    binding: dict[str, Any]
    transaction_id: str
    canonical_selector_projection: dict[str, Any]
    candidate_prompt_projection: dict[str, Any]
    candidate_generation: dict[str, Any]
    candidate_path_replay: dict[str, Any]


def freeze_natural_pack(
    question: str,
    *,
    route: str,
    example_id: str,
    replay: CandidateReplayContext,
    code_sha: str,
) -> NaturalPackContext:
    request = _natural_request(question, replay)
    candidate_route = str(replay.candidate_identity.get("internal_route") or route)
    bundle = EvidenceBundle(
        route=candidate_route or "natural_semantic_pack",
        items=deepcopy(replay.items),
        metadata=deepcopy(replay.bundle_metadata),
    )
    slots = required_semantic_proposition_slots(request)
    identity = _candidate_replay_identity(
        replay,
        code_sha=code_sha,
        example_id=example_id,
        route=route,
        question=question,
    )
    transaction_id = str(identity["transaction_id"])
    (
        records,
        diagnostics,
        source_packing,
        response_schema,
        messages,
        token_measurement,
        dropped_count,
    ) = _prepare_candidate_request(
        request,
        bundle,
        question=question,
        transaction_id=transaction_id,
        replay=replay,
    )
    binding, bound_slots, frozen = _freeze_replay_candidate_pack(
        bundle,
        question=question,
        slots=slots,
        source_packing=source_packing,
        records=records,
        diagnostics=diagnostics,
        transaction_id=transaction_id,
    )
    candidate_generation = _candidate_generation_observation(
        bundle=bundle,
        messages=messages,
        response_schema=response_schema,
        identity=identity,
        route=candidate_route,
        seed=replay.candidate_seed,
        records=records,
        diagnostics=diagnostics,
        token_measurement=token_measurement,
        dropped_count=dropped_count,
    )
    candidate_generation = replay_frozen_candidate_response(
        candidate_generation, replay.online_candidate_response
    )
    loaded, load_reason = load_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        candidate_transaction_id=transaction_id,
    )
    return _natural_pack_context(
        bundle=bundle,
        bound_slots=bound_slots,
        frozen=frozen,
        loaded=loaded,
        load_reason=load_reason,
        binding=binding,
        transaction_id=transaction_id,
        diagnostics=diagnostics,
        candidate_generation=candidate_generation,
        replay=replay,
    )


def _freeze_replay_candidate_pack(
    bundle: EvidenceBundle,
    *,
    question: str,
    slots: list[dict[str, Any]],
    source_packing: Any,
    records: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    transaction_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], Any]:
    binding = _mapping(diagnostics.get("candidate_evidence_set_binding"))
    bound_slots = _bound_slots(diagnostics)
    frozen = freeze_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        slots=slots,
        source_packing=source_packing,
        records=records,
        candidate_transaction_id=transaction_id,
        candidate_binding=binding,
        candidate_required_slots=bound_slots,
    )
    diagnostics.update(
        qasper_candidate_pack_identity_projection(
            frozen,
            candidate_transaction_id=transaction_id,
        )
    )
    return binding, bound_slots, frozen


def _bound_slots(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(slot)
        for slot in diagnostics.get("required_slots") or []
        if isinstance(slot, dict)
    ]


def _natural_pack_context(
    *,
    bundle: EvidenceBundle,
    bound_slots: list[dict[str, Any]],
    frozen: Any,
    loaded: Any,
    load_reason: str,
    binding: dict[str, Any],
    transaction_id: str,
    diagnostics: dict[str, Any],
    candidate_generation: dict[str, Any],
    replay: CandidateReplayContext,
) -> NaturalPackContext:
    return NaturalPackContext(
        bundle=bundle,
        slots=bound_slots,
        frozen=frozen,
        loaded=loaded,
        load_reason=load_reason,
        binding=binding,
        transaction_id=transaction_id,
        canonical_selector_projection=_mapping(
            diagnostics.get("canonical_selector_projection_trace")
        ),
        candidate_prompt_projection=_mapping(
            diagnostics.get("candidate_prompt_projection_trace")
        ),
        candidate_generation=deepcopy(candidate_generation),
        candidate_path_replay=deepcopy(replay.observation),
    )


def _candidate_generation_observation(
    *,
    bundle: EvidenceBundle,
    messages: list[dict[str, Any]],
    response_schema: dict[str, Any],
    identity: dict[str, Any],
    route: str,
    seed: int,
    records: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    token_measurement: dict[str, Any],
    dropped_count: int,
) -> dict[str, Any]:
    observation, _input_digest = _record_candidate_request(
        bundle,
        llm=None,
        messages=messages,
        response_schema=response_schema,
        identity=identity,
        route=route,
        seed=seed,
        evidence=records,
        evidence_diagnostics=diagnostics,
        controlled_candidate="",
        token_measurement=token_measurement,
        request_dropped_count=dropped_count,
    )
    return observation


def _prepare_candidate_request(
    request: Any,
    bundle: EvidenceBundle,
    *,
    question: str,
    transaction_id: str,
    replay: CandidateReplayContext,
) -> tuple[Any, ...]:
    frozen_request = _mapping(replay.online_candidate_request)
    if replay.observation.get("complete") is not True:
        reasons = replay.observation.get("incompleteness_reasons") or []
        detail = ", ".join(str(reason) for reason in reasons)
        if frozen_request.get("complete") is not True:
            raise ValueError(f"frozen candidate request incomplete: {detail}")
        raise ValueError(f"frozen candidate-stage snapshot incomplete: {detail}")
    records, diagnostics, source_packing = _candidate_evidence(
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
    ) = _replay_frozen_candidate_request(
        question,
        records,
        diagnostics,
        candidate_transaction_id=transaction_id,
        frozen_request=frozen_request,
    )
    return (
        records,
        diagnostics,
        source_packing,
        response_schema,
        messages,
        token_measurement,
        dropped_count,
    )


def _replay_frozen_candidate_request(
    question: str,
    records: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    *,
    candidate_transaction_id: str,
    frozen_request: dict[str, Any],
) -> tuple[Any, ...]:
    projection = _mapping(frozen_request.get("candidate_request_projection_trace"))
    selected = _frozen_selected_records(records, projection)
    candidate_dropped = int(
        frozen_request.get("candidate_request_dropped_evidence_count") or 0
    )
    pre_request_dropped = int(
        diagnostics.get("pre_request_dropped_evidence_count") or 0
    )
    if len(records) - len(selected) != candidate_dropped:
        raise ValueError("frozen candidate request drop count mismatch")
    expected_total_dropped = pre_request_dropped + candidate_dropped
    if frozen_request.get("request_dropped_evidence_count") != expected_total_dropped:
        raise ValueError("frozen candidate total drop count mismatch")
    binding = candidate_evidence_set_binding(
        selected,
        question,
        candidate_transaction_id=candidate_transaction_id,
    )
    bound_slots = _bound_candidate_slots(
        diagnostics.get("required_slots", []),
        selected,
        binding=binding,
    )
    replay_diagnostics = candidate_request_diagnostics(
        diagnostics,
        bound_slots,
        binding,
        dropped_count=candidate_dropped,
        pre_request_dropped_count=pre_request_dropped,
    )
    replay_diagnostics["candidate_request_projection_trace"] = deepcopy(projection)
    messages = candidate_messages(
        question,
        selected,
        replay_diagnostics,
        controlled_candidate="",
    )
    serialized_messages = _serialized_messages(messages)
    replay_diagnostics["frozen_candidate_request_replay"] = {
        "contract_id": "qasper_frozen_candidate_request_replay.v1",
        "status": (
            "matched"
            if serialized_messages == frozen_request.get("message_stack")
            else "diverged"
        ),
        "selected_record_ids": [
            str(record.get("evidence_id") or "") for record in selected
        ],
        "selected_record_ids_digest": canonical_digest(
            [str(record.get("evidence_id") or "") for record in selected]
        ),
        "message_stack_digest": canonical_digest(serialized_messages),
        "frozen_message_stack_digest": str(
            frozen_request.get("message_stack_digest") or ""
        ),
    }
    return (
        selected,
        replay_diagnostics,
        messages,
        deepcopy(_mapping(frozen_request.get("token_measurement"))),
        expected_total_dropped,
    )


def _frozen_selected_records(
    records: list[dict[str, Any]],
    projection: dict[str, Any],
) -> list[dict[str, Any]]:
    record_ids = [str(record.get("evidence_id") or "") for record in records]
    decisions = [_mapping(decision) for decision in projection.get("decisions") or []]
    decision_ids = [str(decision.get("evidence_id") or "") for decision in decisions]
    if decision_ids != record_ids or len(set(record_ids)) != len(record_ids):
        raise ValueError("frozen candidate request record identity mismatch")
    selected_ids = {
        str(decision.get("evidence_id") or "")
        for decision in decisions
        if decision.get("selected") is True
    }
    selected = [
        deepcopy(record)
        for record in records
        if str(record.get("evidence_id") or "") in selected_ids
    ]
    if len(selected) != int(projection.get("selected_record_count") or 0):
        raise ValueError("frozen candidate request selected count mismatch")
    return selected


def _natural_request(question: str, replay: CandidateReplayContext) -> Any:
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="qasper",
        dataset_family="qasper",
        answer_type="boolean",
        question=question,
        query=question,
        query_plan=deepcopy(replay.query_plan),
    )
    if replay.max_context_length is not None:
        request.max_context_length = replay.max_context_length
    return request


def _candidate_replay_identity(
    replay: CandidateReplayContext,
    *,
    code_sha: str,
    example_id: str,
    route: str,
    question: str,
) -> dict[str, Any]:
    identity = deepcopy(replay.candidate_identity)
    if identity.get("transaction_id"):
        return identity
    transaction_id = (
        "natural-probe:"
        + canonical_digest(
            {
                "code_sha": code_sha,
                "example_id": example_id,
                "route": route,
                "question": question,
            }
        )[:24]
    )
    return {
        "trace_group_id": f"natural-probe:{example_id}",
        "benchmark_route_id": route,
        "internal_route": route,
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:candidate_generation:1",
        "generation_sequence": 0,
        "predecessor_transaction_id": "",
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
