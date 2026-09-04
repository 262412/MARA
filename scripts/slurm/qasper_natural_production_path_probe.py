from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning.mara_qasper_semantic_pack import (
    qasper_canonical_evidence_plans,
    qasper_canonical_selector_bindings,
    qasper_source_packing_observation,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    semantic_proposition_verifier_prompt,
)
from ktem.reasoning.mara_semantic_proposition_transaction import (
    run_semantic_proposition_transaction,
)

from scripts.slurm.qasper_natural_production_path_support import (
    BOUND_STATES as _BOUND_STATES,
)
from scripts.slurm.qasper_natural_production_path_support import (
    PRODUCTION_CONTRACT as _PRODUCTION_CONTRACT,
)
from scripts.slurm.qasper_natural_production_path_support import _mapping
from scripts.slurm.qasper_natural_production_path_support import (
    audit_replay_response as _audit_replay_response,
)
from scripts.slurm.qasper_natural_production_path_support import (
    authority_observation as _authority_observation,
)
from scripts.slurm.qasper_natural_production_path_support import (
    candidate_label as _candidate_label,
)
from scripts.slurm.qasper_natural_production_path_support import (
    finish_production_path as _finish_production_path,
)
from scripts.slurm.qasper_natural_production_path_support import (
    frozen_plan_projection as _frozen_plan_projection,
)
from scripts.slurm.qasper_natural_production_path_support import (
    fusion_replay_prediction,
)
from scripts.slurm.qasper_natural_production_path_support import (
    not_applicable_production_path as _not_applicable_production_path,
)
from scripts.slurm.qasper_natural_production_path_support import (
    production_failure_path as _production_failure_path,
)
from scripts.slurm.qasper_natural_production_path_support import (
    production_path_result as _production_path_result,
)
from scripts.slurm.qasper_natural_production_path_support import (
    production_request as _production_request,
)
from scripts.slurm.qasper_natural_production_path_support import (
    record_production_verifier_trace as _record_production_verifier_trace,
)
from scripts.slurm.qasper_natural_production_path_support import (
    source_semantic_trace_observation as _source_semantic_trace_observation,
)
from scripts.slurm.qasper_natural_production_path_support import (
    source_stage_response as _source_stage_response,
)

__all__ = [
    "production_authority_probe",
    "fusion_replay_prediction",
    "_BOUND_STATES",
    "_PRODUCTION_CONTRACT",
    "_audit_replay_response",
    "_authority_observation",
    "_candidate_label",
    "_finish_production_path",
    "_frozen_plan_projection",
    "_not_applicable_production_path",
    "_production_failure_path",
    "_production_request",
    "_production_path_result",
    "_record_production_verifier_trace",
    "_source_semantic_trace_observation",
    "_source_stage_response",
    "_mapping",
]


def production_authority_probe(
    row: Mapping[str, Any],
    context: Any,
    *,
    question: str,
    candidate_generation: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay the real transaction, preflight and final boolean authority."""

    bundle = context.bundle
    source_metadata = _mapping(row.get("evidence_metadata"))
    metadata = deepcopy(bundle.metadata)
    candidate = _candidate_label(candidate_generation, source_metadata, row)
    source_trace = _source_semantic_trace_observation(source_metadata)
    if str(context.binding.get("binding_state") or "") not in _BOUND_STATES:
        return _not_applicable_production_path(candidate, source_trace=source_trace)

    raw_proposal = _source_stage_response(source_metadata, "proposal")
    plan_id = _proposal_plan_id(raw_proposal)
    projection, projection_reason = _frozen_plan_projection(
        bundle, context, question=question, plan_id=plan_id
    )
    projection_observation = {
        "called": True,
        "status": "passed" if projection is not None else "failed",
        "reason": projection_reason,
        "plan_id": plan_id,
        "plan_digest": str(getattr(projection, "plan_digest", "") or ""),
    }
    raw_audit = _source_stage_response(source_metadata, "audit")
    raw_audit, audit_response_source = _audit_replay_response(raw_audit, projection)
    try:
        outcome = _run_semantic_transaction(
            context,
            bundle,
            metadata,
            question=question,
            candidate=candidate,
            candidate_generation=candidate_generation,
            source_metadata=source_metadata,
            raw_proposal=raw_proposal,
            raw_audit=raw_audit,
        )
    except (TypeError, ValueError) as exc:
        return _production_failure_path(
            candidate,
            source_trace=source_trace,
            projection=projection_observation,
            audit_response_source=audit_response_source,
            reason=f"semantic_transaction_setup_failed:{exc}",
        )
    return _finish_production_path(
        metadata,
        context=context,
        bundle=bundle,
        outcome=outcome,
        candidate=candidate,
        source_metadata=source_metadata,
        question=question,
        source_trace=source_trace,
        projection=projection_observation,
        audit_response_source=audit_response_source,
    )


def _run_semantic_transaction(
    context: Any,
    bundle: EvidenceBundle,
    metadata: Mapping[str, Any],
    *,
    question: str,
    candidate: str,
    candidate_generation: Mapping[str, Any],
    source_metadata: Mapping[str, Any],
    raw_proposal: str,
    raw_audit: str,
) -> Any:
    prompt = semantic_proposition_verifier_prompt(
        question, context.slots, context.frozen.records, candidate=candidate
    )
    pack = _mapping(metadata.get("qasper_canonical_semantic_pack"))
    return run_semantic_proposition_transaction(
        _StaticLLM(raw_proposal, "natural-probe-proposal-v1"),
        _StaticLLM(raw_audit, "natural-probe-auditor-v1"),
        prompt,
        question=question,
        packed=deepcopy(context.frozen.records),
        slots=deepcopy(context.slots),
        proposal_model="natural-probe-proposal-v1",
        audit_model="natural-probe-auditor-v1",
        seed=_candidate_seed(candidate_generation, source_metadata),
        release_mode=True,
        semantic_pack_digest=context.frozen.semantic_pack_digest,
        canonical_span_universe_digest=str(pack.get("span_universe_digest") or ""),
        candidate_transaction_id=context.transaction_id,
        allowed_proposition_slot_bindings=qasper_canonical_selector_bindings(
            context.frozen.records
        ),
        allowed_proposition_evidence_plans=qasper_canonical_evidence_plans(bundle),
        plan_construction_trace=deepcopy(
            context.binding.get("plan_construction_trace") or {}
        ),
        source_packing_observation=qasper_source_packing_observation(bundle),
        capture_debug_trace=True,
        transaction_id=context.transaction_id,
        attempt_namespace="natural_probe",
    )


class _StaticLLM:
    """Supply a recorded response without pretending characters are tokens."""

    def __init__(self, text: str, model_name: str) -> None:
        self.text = str(text or "")
        self.model_name = model_name

    def __call__(self, _messages: Any, **_parameters: Any) -> Any:
        return SimpleNamespace(
            text=self.text,
            completion_tokens=0,
            prompt_tokens=0,
            finish_reason="stop",
        )


def _candidate_seed(
    candidate_generation: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> int:
    for source in (
        candidate_generation,
        _mapping(metadata.get("qasper_candidate_generation")),
    ):
        value = source.get("effective_seed")
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 20260724


def _proposal_plan_id(raw_proposal: str) -> str:
    try:
        payload = json.loads(raw_proposal)
    except (TypeError, json.JSONDecodeError):
        return ""
    return (
        str(payload.get("canonical_evidence_plan_id") or "")
        if isinstance(payload, dict)
        else ""
    )
