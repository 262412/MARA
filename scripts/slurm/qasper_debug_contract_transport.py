from __future__ import annotations

from typing import Any

from scripts.slurm.qasper_debug_contract_probe_cases import ProbeCase

TRANSPORT_CONTRACT = "qasper_candidate_transport_identity.v1"


def controlled_input_payload(
    case: ProbeCase,
    generation_candidate: str,
    verifier_candidate: str,
    generator: dict[str, Any],
) -> dict[str, Any]:
    requested = _candidate(
        generator.get("requested_controlled_candidate") or case.controlled_candidate
    )
    preserved = bool(
        generator.get("candidate_transport_identity_preserved") is True
        and (
            not requested
            or all(
                value == requested
                for value in (
                    _candidate(generator.get("provider_raw_candidate")),
                    _candidate(generator.get("cleaned_candidate")),
                    _candidate(generator.get("typed_candidate")),
                    _candidate(verifier_candidate),
                )
            )
        )
    )
    failed = generator.get("failure_reason") == "candidate_transport_failed"
    return {
        "contract_id": TRANSPORT_CONTRACT,
        "mode": "controlled_original_candidate" if requested else "none",
        "generator_candidate": generation_candidate,
        "original_candidate": requested,
        "requested_candidate": requested,
        "provider_raw_candidate": str(generator.get("provider_raw_candidate") or ""),
        "cleaned_candidate": str(generator.get("cleaned_candidate") or ""),
        "typed_candidate": str(generator.get("typed_candidate") or ""),
        "verifier_input_candidate": verifier_candidate,
        "transport_identity_preserved": preserved,
        "candidate_transport_status": str(
            generator.get("candidate_transport_status") or "not_started"
        ),
        "candidate_transport_failure": ("candidate_transport_failed" if failed else ""),
        "verifier_transport_status": (
            "verifier_not_started" if failed else "verifier_started"
        ),
        "auditor_transport_status": (
            "auditor_not_started" if failed else "auditor_started"
        ),
        "evidence_switch": case.controlled_fault or "none",
        "payload_fixture": case.payload_fixture or "none",
        "quality_failure": False,
    }


def assert_controlled_candidate_transport(
    case: ProbeCase,
    row: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    controlled = row.get("controlled_input")
    if not isinstance(controlled, dict):
        raise RuntimeError(f"{case.case_id}: controlled-input provenance is missing")
    requested = _candidate(controlled.get("requested_candidate"))
    if not requested:
        return controlled, ""
    if controlled.get("contract_id") != TRANSPORT_CONTRACT:
        raise RuntimeError(
            f"{case.case_id}: candidate transport contract identity is missing"
        )
    transported = (
        _candidate(controlled.get("provider_raw_candidate")),
        _candidate(controlled.get("cleaned_candidate")),
        _candidate(controlled.get("typed_candidate")),
        _candidate(controlled.get("verifier_input_candidate")),
    )
    if (
        requested != case.controlled_candidate
        or any(value != requested for value in transported)
        or controlled.get("transport_identity_preserved") is not True
    ):
        raise RuntimeError(
            f"{case.case_id}: candidate_transport identity mismatch; "
            f"requested={requested!r}, transported={transported!r}"
        )
    return controlled, requested


def _candidate(value: object) -> str:
    return str(value or "").strip().casefold()
