from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from scripts.slurm.qasper_debug_contract_probe_cases import (
    ProbeCase,
    _build_request_and_bundle,
    _digest,
)


def _response_text(response: Any) -> str:
    value = getattr(response, "text", None)
    if value is None:
        value = getattr(response, "content", None)
    if isinstance(value, list):
        value = "".join(
            str(item.get("text") or "") if isinstance(item, dict) else str(item)
            for item in value
        )
    return str(value or "")


def _response_finish_reason(response: Any) -> str:
    metadata = getattr(response, "additional_kwargs", None)
    if not isinstance(metadata, dict):
        metadata = getattr(response, "response_metadata", None)
    if isinstance(metadata, dict):
        return str(metadata.get("finish_reason") or metadata.get("finish") or "")
    return ""


@dataclass(frozen=True)
class ProviderIdentity:
    """The non-secret provider identity used by one probe judgment source."""

    base_url: str
    model: str
    role: str

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.strip().rstrip("/").casefold()

    @property
    def normalized_model(self) -> str:
        return self.model.strip().casefold()

    def as_dict(self) -> dict[str, str]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "role": self.role,
        }


def validate_heterogeneous_provider_config(
    *,
    base_url: str | None,
    model: str | None,
    auditor_base_url: str | None,
    auditor_model: str | None,
) -> tuple[ProviderIdentity, ProviderIdentity]:
    """Require explicit proposer/auditor endpoints and distinct model names."""

    proposer = ProviderIdentity(
        base_url=str(base_url or "").strip(),
        model=str(model or "").strip(),
        role="proposer",
    )
    auditor = ProviderIdentity(
        base_url=str(auditor_base_url or "").strip(),
        model=str(auditor_model or "").strip(),
        role="auditor",
    )
    missing = [
        label
        for label, value in (
            ("proposer endpoint", proposer.base_url),
            ("proposer model", proposer.model),
            ("auditor endpoint", auditor.base_url),
            ("auditor model", auditor.model),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "heterogeneous contract probe requires explicit " + ", ".join(missing)
        )
    if proposer.normalized_model == auditor.normalized_model:
        raise ValueError(
            "heterogeneous contract probe requires distinct proposer and "
            "auditor models; same model/provider is not an independent audit"
        )
    return proposer, auditor


class _RecordingChatModel:
    """Record transport facts while returning the provider response unchanged."""

    def __init__(
        self,
        inner: Any,
        *,
        case_id: str,
        calls: list[dict[str, Any]],
        provider_identity: ProviderIdentity,
    ) -> None:
        self._inner = inner
        self._case_id = case_id
        self._calls = calls
        self.provider_identity = provider_identity
        self.model_name = provider_identity.model
        self.model = provider_identity.model
        self.base_url = provider_identity.base_url

    def __call__(self, messages: Any, **kwargs: Any) -> Any:
        response_format = kwargs.get("response_format")
        schema = (
            response_format.get("json_schema", {})
            if isinstance(response_format, dict)
            else {}
        )
        stage = str(schema.get("name") or "provider_call")
        call_id = f"{self._case_id}:{stage}:{len(self._calls) + 1}"
        request_payload = {
            "messages": messages,
            "kwargs": kwargs,
            "model": self.model_name,
        }
        response = self._inner(messages, **kwargs)
        raw = _response_text(response)
        self._calls.append(
            {
                "call_id": call_id,
                "case_id": self._case_id,
                "stage": stage,
                "provider_role": self.provider_identity.role,
                "base_url": self.provider_identity.base_url,
                "model": self.provider_identity.model,
                "provider_identity": self.provider_identity.as_dict(),
                "transport_mode": (
                    "controlled_pre_audit_fixture"
                    if getattr(self._inner, "controlled_pre_audit", False)
                    else "live_provider"
                ),
                "request_digest": _digest(request_payload),
                "response_digest": _digest(raw),
                "finish_reason": _response_finish_reason(response),
            }
        )
        return response


def _default_model_factory(
    *,
    base_url: str,
    model: str,
    timeout_seconds: float,
    role: str,
    case_id: str,
) -> Any:
    """Construct the configured production provider; no domain parsing occurs here."""

    from kotaemon.llms import ChatOpenAI

    del role, case_id
    return ChatOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", "local"),
        base_url=base_url,
        model=model,
        temperature=0,
        timeout=timeout_seconds,
        max_retries=0,
    )


def _pipeline(proposal_llm: Any, *, audit_llm: Any) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(
        answering_pipeline=SimpleNamespace(llm=proposal_llm),
        semantic_entailment_auditor_llm=audit_llm,
        semantic_proposition_debug_trace=True,
        semantic_proposition_release_mode=True,
    )


def _model_clients(
    case: ProbeCase,
    *,
    base_url: str,
    model: str,
    auditor_base_url: str,
    auditor_model: str,
    timeout_seconds: float,
    model_factory: Callable[..., Any],
) -> tuple[Any, Any, list[dict[str, Any]]]:
    proposer_identity, auditor_identity = validate_heterogeneous_provider_config(
        base_url=base_url,
        model=model,
        auditor_base_url=auditor_base_url,
        auditor_model=auditor_model,
    )
    calls: list[dict[str, Any]] = []
    proposal_inner = model_factory(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        role="candidate_and_proposal",
        case_id=case.case_id,
    )
    auditor_inner = model_factory(
        base_url=auditor_base_url,
        model=auditor_model,
        timeout_seconds=timeout_seconds,
        role="auditor",
        case_id=case.case_id,
    )
    proposal_llm = _RecordingChatModel(
        proposal_inner,
        case_id=case.case_id,
        calls=calls,
        provider_identity=proposer_identity,
    )
    auditor_llm = _RecordingChatModel(
        auditor_inner,
        case_id=case.case_id,
        calls=calls,
        provider_identity=auditor_identity,
    )
    return _pipeline(proposal_llm, audit_llm=auditor_llm), auditor_llm, calls


def _execute_case(
    case: ProbeCase,
    index: int,
    *,
    base_url: str,
    model: str,
    auditor_base_url: str,
    auditor_model: str,
    timeout_seconds: float,
    model_factory: Callable[..., Any],
) -> tuple[str, str, Any, list[dict[str, Any]]]:
    from ktem.docqa.controller import RetrieveDecision
    from ktem.docqa.execution_results import verified_result
    from ktem.docqa.route_selection import ControllerDecision
    from ktem.docqa.verification import verify_decision
    from ktem.reasoning.mara_qasper_candidate import generate_qasper_typed_candidate
    from ktem.reasoning.mara_semantic_proposition_verifier import (
        build_semantic_proposition_verifier,
    )

    request, bundle = _build_request_and_bundle(case, index)
    pipeline, auditor_llm, calls = _model_clients(
        case,
        base_url=base_url,
        model=model,
        auditor_base_url=auditor_base_url,
        auditor_model=auditor_model,
        timeout_seconds=timeout_seconds,
        model_factory=model_factory,
    )
    candidate = generate_qasper_typed_candidate(pipeline, request, bundle)
    decision = ControllerDecision(
        route="contract_probe",
        legacy_route="contract_probe",
        policy="contract_probe",
        controller_mode="contract_probe",
        requires_retrieval=True,
        reason="live provider contract probe",
    )
    retrieve_decision = RetrieveDecision(
        status="good",
        reason="live contract probe evidence",
        retry=False,
    )
    proposition_verifier = build_semantic_proposition_verifier(
        pipeline,
        audit_llm=auditor_llm,
    )

    def _verify(request_: Any, retrieve_: Any, bundle_: Any, answer_: str) -> Any:
        return verify_decision(
            request_,
            retrieve_,
            bundle_,
            answer_,
            proposition_verifier=proposition_verifier,
        )

    execution = verified_result(
        request,
        decision,
        retrieve_decision,
        bundle,
        candidate,
        None,
        {"contract_probe": True},
        verify=_verify,
    )
    return candidate, candidate, execution, calls


def _attach_call_evidence(
    execution: Any,
    calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    live_calls = deepcopy(calls)
    identities = _provider_identities_from_calls(live_calls)
    # The call records are transport provenance only; all domain fields below
    # remain the returned production objects.  Preserve them in both copies
    # used by the artifact/audit readers.
    execution.evidence_bundle.metadata["contract_probe_live_calls"] = live_calls
    execution.evidence_bundle.metadata[
        "contract_probe_provider_identities"
    ] = identities
    if isinstance(execution.engine_terminal_evidence_bundle, dict):
        terminal_metadata = execution.engine_terminal_evidence_bundle.setdefault(
            "metadata", {}
        )
        if isinstance(terminal_metadata, dict):
            terminal_metadata["contract_probe_live_calls"] = live_calls
            terminal_metadata["contract_probe_provider_identities"] = identities
    return live_calls


def _provider_identities_from_calls(
    calls: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    """Project recorded transport identities without inferring missing roles."""

    identities: dict[str, set[tuple[str, str]]] = {
        "proposer": set(),
        "auditor": set(),
    }
    for call in calls:
        if not isinstance(call, dict):
            continue
        role = str(call.get("provider_role") or "").strip().casefold()
        if role not in identities:
            continue
        base_url = str(call.get("base_url") or "").strip()
        model = str(call.get("model") or "").strip()
        if base_url and model:
            identities[role].add((base_url, model))
    return {
        role: [
            {"base_url": base_url, "model": model, "role": role}
            for base_url, model in sorted(values)
        ]
        for role, values in identities.items()
    }
