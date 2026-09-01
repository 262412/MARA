from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import request_planning_question

from kotaemon.base import SystemMessage

from .mara_answer_type_contract import request_answer_type
from .mara_qasper_candidate_budget import QASPER_CANDIDATE_MAX_MODEL_LEN  # noqa: F401
from .mara_qasper_candidate_budget import QASPER_CANDIDATE_TOKEN_HEADROOM  # noqa: F401
from .mara_qasper_candidate_budget import (  # noqa: F401
    QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
    QASPER_CANDIDATE_MAX_TOKENS,
)
from .mara_qasper_candidate_budget import (
    candidate_generation_trace as _candidate_generation_trace,
)
from .mara_qasper_candidate_budget import (  # noqa: F401
    candidate_input_token_measurement,
    estimate_qasper_candidate_input_tokens,
)
from .mara_qasper_candidate_evidence import (  # noqa: F401
    candidate_evidence_set_binding as _candidate_evidence_set_binding,
)
from .mara_qasper_candidate_evidence import (  # noqa: F401
    candidate_selector_options as _candidate_selector_options,
)
from .mara_qasper_candidate_identity import candidate_digest as _digest
from .mara_qasper_candidate_identity import candidate_model_name as _model_name
from .mara_qasper_candidate_identity import (
    candidate_transaction_identity as _transaction_identity,
)
from .mara_qasper_candidate_identity import effective_candidate_seed
from .mara_qasper_candidate_prompt import (
    _bound_candidate_slots as _prompt_bound_candidate_slots,
)
from .mara_qasper_candidate_prompt import (  # noqa: F401
    _candidate_evidence,
    _candidate_prompt,
)
from .mara_qasper_candidate_request import (  # noqa: F401
    candidate_messages as _candidate_messages,
)
from .mara_qasper_candidate_request import (
    fit_candidate_request as _fit_candidate_request,
)
from .mara_qasper_candidate_transport import (  # noqa: F401 - compatibility re-export
    QASPER_CANDIDATE_MAX_RESPONSE_CHARS,
    QASPER_CANDIDATE_RESPONSE_CONTRACT,
    QASPER_CANDIDATES,
)
from .mara_qasper_candidate_transport import candidate_attempt as _candidate_attempt
from .mara_qasper_candidate_transport import (
    candidate_response_state as _candidate_response_state,
)
from .mara_qasper_candidate_transport import (
    candidate_response_trace_fields as _candidate_response_trace_fields,
)
from .mara_qasper_candidate_transport import (  # noqa: F401 - compatibility re-export
    parse_qasper_candidate,
    qasper_candidate_response_format,
)
from .mara_qasper_semantic_pack import freeze_qasper_canonical_semantic_pack
from .mara_qasper_semantic_pack_observation import (
    qasper_candidate_pack_identity_projection,
)
from .mara_semantic_proposition_debug import provider_failure
from .mara_semantic_proposition_packing import (
    SemanticPropositionEvidencePacking,
    required_semantic_proposition_slots,
)

QASPER_CANDIDATE_GENERATION_CONTRACT = "qasper_typed_candidate_generation.v2"
QASPER_CANDIDATE_DEFAULT_SEED = 20260724

LOGGER = logging.getLogger(__name__)

# Preserve the existing private test/debug seam after moving prompt construction.
_bound_candidate_slots = _prompt_bound_candidate_slots


def qasper_typed_candidate_request(request: Any) -> bool:
    domain = str(getattr(request, "verification_domain", "") or "").casefold()
    origin = str(getattr(request, "origin", "") or "").casefold()
    return (
        origin == "benchmark"
        and (domain == "qasper" or domain.startswith("qasper_"))
        and request_answer_type(request) == "boolean"
    )


def generate_qasper_typed_candidate(
    pipeline: Any,
    request: Any,
    bundle: EvidenceBundle,
) -> str:
    llm = _answering_llm(pipeline)
    question = request_planning_question(request)
    seed = _candidate_seed(request)
    route = str(bundle.route or "")
    controlled_candidate = _contract_probe_original_candidate(request, route)
    identity = _candidate_transaction(request, bundle, route, seed)
    evidence, evidence_diagnostics, source_packing = _candidate_evidence(
        request,
        question,
        bundle,
        candidate_transaction_id=identity["transaction_id"],
    )
    response_schema = qasper_candidate_response_format(
        controlled_candidate=controlled_candidate
    )
    (
        evidence,
        evidence_diagnostics,
        messages,
        token_measurement,
        request_dropped_count,
    ) = _fit_candidate_request(
        llm,
        question,
        evidence,
        evidence_diagnostics,
        response_schema=response_schema,
        controlled_candidate=controlled_candidate,
        candidate_transaction_id=identity["transaction_id"],
    )
    _freeze_candidate_semantic_pack(
        bundle,
        request,
        question,
        source_packing,
        evidence,
        evidence_diagnostics,
        identity["transaction_id"],
    )
    trace, input_digest = _record_candidate_request(
        bundle,
        llm=llm,
        messages=messages,
        response_schema=response_schema,
        identity=identity,
        route=route,
        seed=seed,
        evidence=evidence,
        evidence_diagnostics=evidence_diagnostics,
        controlled_candidate=controlled_candidate,
        token_measurement=token_measurement,
        request_dropped_count=request_dropped_count,
    )
    if not _candidate_request_ready(llm, token_measurement, trace, identity):
        return ""
    return _generate_candidate_response(
        llm,
        messages,
        trace,
        identity,
        input_digest,
        seed,
        response_schema,
        controlled_candidate,
    )


def _record_candidate_request(
    bundle: EvidenceBundle,
    *,
    llm: Any,
    messages: list[Any],
    response_schema: dict[str, Any],
    identity: dict[str, Any],
    route: str,
    seed: int,
    evidence: list[dict[str, Any]],
    evidence_diagnostics: dict[str, Any],
    controlled_candidate: str,
    token_measurement: dict[str, Any],
    request_dropped_count: int,
) -> tuple[dict[str, Any], str]:
    serialized_messages = _serialized_messages(messages)
    schema_digest = _digest(response_schema)
    input_digest = _digest(
        {
            "messages": serialized_messages,
            "response_schema_digest": schema_digest,
            "seed": seed,
            "route": route,
            "benchmark_route_id": identity.get("benchmark_route_id", ""),
        }
    )
    trace = _candidate_generation_trace(
        model=_model_name(llm),
        identity=identity,
        route=route,
        seed=seed,
        serialized_messages=serialized_messages,
        input_digest=input_digest,
        evidence=evidence,
        evidence_diagnostics=evidence_diagnostics,
        controlled_candidate=controlled_candidate,
        response_schema_digest=schema_digest,
        token_measurement=token_measurement,
        request_dropped_count=request_dropped_count,
    )
    bundle.metadata["qasper_candidate_generation"] = trace
    return trace, input_digest


def _candidate_seed(request: Any) -> int:
    return effective_candidate_seed(
        request,
        default_seed=QASPER_CANDIDATE_DEFAULT_SEED,
    )


def _candidate_transaction(
    request: Any,
    bundle: EvidenceBundle,
    route: str,
    seed: int,
) -> dict[str, Any]:
    predecessor = str(
        bundle.metadata.get("qasper_candidate_predecessor_transaction_id") or ""
    )
    return _transaction_identity(
        request,
        route,
        seed,
        generation_sequence=_candidate_generation_sequence(bundle),
        predecessor_transaction_id=predecessor,
    )


def _freeze_candidate_semantic_pack(
    bundle: EvidenceBundle,
    request: Any,
    question: str,
    source_packing: SemanticPropositionEvidencePacking,
    evidence: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    transaction_id: str,
) -> None:
    packing = freeze_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        slots=required_semantic_proposition_slots(request),
        source_packing=source_packing,
        records=evidence,
        candidate_transaction_id=transaction_id,
        candidate_binding=diagnostics.get("candidate_evidence_set_binding"),
        candidate_required_slots=diagnostics.get("required_slots"),
    )
    diagnostics.update(
        qasper_candidate_pack_identity_projection(
            packing,
            candidate_transaction_id=transaction_id,
        )
    )


def _candidate_generation_sequence(bundle: EvidenceBundle) -> int:
    value = bundle.metadata.get("qasper_candidate_generation_sequence", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("qasper_candidate_generation_sequence_invalid")
    return value


def _candidate_request_ready(
    llm: Any | None,
    token_measurement: dict[str, Any],
    trace: dict[str, Any],
    identity: dict[str, str],
) -> bool:
    if llm is None:
        trace.update(status="failed", failure_reason="generator_llm_unavailable")
        return False
    if token_measurement.get("tokenizer_failed"):
        failure_detail = (
            "tokenizer_endpoint="
            f"{token_measurement.get('tokenizer_endpoint', '')}; "
            "tokenizer_method="
            f"{token_measurement.get('tokenizer_method', '')}; "
            "tokenizer_failure_reason="
            f"{token_measurement.get('tokenizer_failure_reason', '')}"
        )
        trace.update(
            status="failed",
            failure_reason="provider_tokenizer_failed",
            provider_failure_reason="provider_tokenizer_failed",
            provider_failure_detail=failure_detail,
        )
        trace["attempts"] = [
            {
                "attempt_id": identity["attempt_id"],
                "status": "provider_failed",
                "failure_reason": "provider_tokenizer_failed",
                "failure_detail": failure_detail,
            }
        ]
        return False
    if (
        token_measurement["estimated_input_tokens"]
        > QASPER_CANDIDATE_INPUT_TOKEN_BUDGET
    ):
        trace.update(status="failed", failure_reason="candidate_input_budget_exceeded")
        return False
    return True


def _contract_probe_original_candidate(request: Any, route: str) -> str:
    trace_context = getattr(request, "trace_context", None)
    trace_context = trace_context if isinstance(trace_context, dict) else {}
    if "contract_probe_original_candidate" not in trace_context:
        return ""
    candidate = (
        str(trace_context.get("contract_probe_original_candidate") or "")
        .strip()
        .casefold()
    )
    eligible = bool(
        route == "contract_probe"
        and str(getattr(request, "origin", "") or "").casefold() == "benchmark"
        and str(getattr(request, "verification_domain", "") or "").casefold()
        == "qasper"
    )
    if not eligible or candidate not in QASPER_CANDIDATES:
        raise ValueError("invalid controlled QASPER contract-probe candidate")
    return candidate


def _generate_candidate_response(
    llm: Any,
    messages: list[Any],
    trace: dict[str, Any],
    identity: dict[str, str],
    input_digest: str,
    seed: int,
    response_schema: dict[str, Any],
    controlled_candidate: str,
) -> str:
    try:
        response = llm(
            messages,
            max_tokens=QASPER_CANDIDATE_MAX_TOKENS,
            response_format=response_schema,
            temperature=0,
            top_p=1,
            seed=seed,
        )
    except Exception as exc:
        LOGGER.exception("QASPER typed candidate generation failed")
        reason, detail = provider_failure(exc)
        trace.update(
            status="failed",
            failure_reason=reason,
            provider_failure_reason=reason,
            provider_failure_detail=detail,
        )
        trace["attempts"] = [
            {
                "attempt_id": identity["attempt_id"],
                "status": "provider_failed",
                "failure_reason": reason,
                "failure_detail": detail,
            }
        ]
        return ""

    return _record_candidate_response(
        response,
        trace,
        identity,
        input_digest,
        controlled_candidate,
    )


def _record_candidate_response(
    response: Any,
    trace: dict[str, Any],
    identity: dict[str, str],
    input_digest: str,
    controlled_candidate: str,
) -> str:
    state = _candidate_response_state(
        response,
        controlled_candidate=controlled_candidate,
    )
    trace.update(**_candidate_response_trace_fields(state))
    trace["attempts"] = [_candidate_attempt(state, identity, input_digest)]
    trace["model_decision"] = _candidate_model_decision(trace, state)
    return str(state["verifier_input_candidate"])


def _candidate_model_decision(
    trace: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    binding = trace.get("candidate_evidence_set_binding")
    binding = binding if isinstance(binding, dict) else {}
    plan_trace = binding.get("plan_construction_trace")
    plan_trace = plan_trace if isinstance(plan_trace, dict) else {}
    valid_counts = plan_trace.get("valid_candidate_counts")
    valid_counts = valid_counts if isinstance(valid_counts, dict) else {}
    legal_plan_count = sum(int(value or 0) for value in valid_counts.values())
    decision = str(state.get("typed_candidate") or "")
    context = {
        "input_digest": str(trace.get("input_digest") or ""),
        "evidence_digest": str(trace.get("evidence_digest") or ""),
        "binding_digest": str(binding.get("binding_digest") or ""),
        "binding_state": str(binding.get("binding_state") or ""),
        "legal_plan_count": legal_plan_count,
        "plan_candidate_decisions_digest": str(
            plan_trace.get("candidate_decisions_digest") or ""
        ),
        "decision_plan_alignment": _candidate_plan_alignment(
            decision,
            legal_plan_count=legal_plan_count,
        ),
    }
    return {
        "contract_id": "qasper_model_candidate_decision.v1",
        "status": str(state.get("status") or ""),
        "decision": decision,
        "decision_origin": "model_output",
        "rationale_status": "not_requested_by_low_entropy_contract",
        "decision_context": context,
        "decision_context_digest": _digest(context),
        "raw_response_digest": str(state.get("raw_response_digest") or ""),
    }


def _candidate_plan_alignment(decision: str, *, legal_plan_count: int) -> str:
    if decision == "unanswerable":
        return (
            "aligned_no_legal_local_plan"
            if legal_plan_count == 0
            else "conflicts_with_legal_local_plan"
        )
    return (
        "candidate_without_legal_local_plan"
        if legal_plan_count == 0
        else "locally_plan_eligible"
    )


def _answering_llm(pipeline: Any) -> Any | None:
    answering_pipeline = getattr(pipeline, "answering_pipeline", None)
    llm = getattr(answering_pipeline, "llm", None)
    return llm if callable(llm) else None


def _serialized_messages(messages: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "role": "system" if isinstance(message, SystemMessage) else "user",
            "content": deepcopy(message.content),
        }
        for index, message in enumerate(messages)
    ]
