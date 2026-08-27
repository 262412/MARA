from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class NaturalQualityPayloadFixture:
    """A provider payload mutation derived from a natural-quality failure."""

    fixture_id: str
    proposal_judgment: str
    signal: str
    mutation: str


NATURAL_QUALITY_PAYLOAD_FIXTURES: tuple[NaturalQualityPayloadFixture, ...] = (
    NaturalQualityPayloadFixture(
        "proposer_over_declares_actor_quantifier",
        "supported",
        "support",
        "append_quantifier_to_bindings",
    ),
    NaturalQualityPayloadFixture(
        "title_only_span_binds_relation_object",
        "supported",
        "support",
        "none",
    ),
    NaturalQualityPayloadFixture(
        "proposer_slot_expectations_differ_from_verified_slot_evidence",
        "supported",
        "support",
        "none",
    ),
    NaturalQualityPayloadFixture(
        "unknown_assessment_duplicate_unresolved_slots",
        "unknown",
        "undetermined",
        "duplicate_unknown_slots",
    ),
)

_NATURAL_QUALITY_FIXTURES = {
    fixture.fixture_id: fixture for fixture in NATURAL_QUALITY_PAYLOAD_FIXTURES
}


def natural_quality_payload_fixture(
    fixture_id: str,
    schema: dict[str, object],
    *,
    candidate: str,
    selector: str,
    evidence_text: str,
) -> dict[str, object]:
    """Build one schema-shaped natural-quality-derived invalid payload.

    The base payload is generated with the same schema and evidence selectors
    used by the heterogeneous provider double. Only the requested contract
    mutation is applied; no answer label or benchmark gold is introduced.
    """

    try:
        fixture = _NATURAL_QUALITY_FIXTURES[fixture_id]
    except KeyError as exc:
        raise ValueError(
            f"unknown natural-quality payload fixture: {fixture_id}"
        ) from exc
    # Import lazily so the legacy provider-support module can re-export this
    # fixture API without a module import cycle.
    from benchmark.tests.qasper_contract_probe_provider_support import (
        _proposal_payload,
    )

    payload = _proposal_payload(
        schema,
        proposal_judgment=fixture.proposal_judgment,
        candidate=candidate,
        selector=selector,
        evidence_text=evidence_text,
        signal=fixture.signal,
        source={},
    )
    if fixture.mutation == "append_quantifier_to_bindings":
        premises = payload.get("premises")
        if not isinstance(premises, list) or not premises:
            raise RuntimeError("natural-quality over-declaration premise missing")
        premise = premises[0]
        if not isinstance(premise, dict):
            raise RuntimeError("natural-quality over-declaration premise invalid")
        bindings = premise.get("binds_proposition_slots")
        if not isinstance(bindings, list):
            raise RuntimeError("natural-quality over-declaration bindings missing")
        premise["binds_proposition_slots"] = [*bindings, "quantifier"]
    elif fixture.mutation == "duplicate_unknown_slots":
        assessment = payload.get("unknown_assessment")
        if not isinstance(assessment, dict):
            raise RuntimeError("natural-quality duplicate assessment missing")
        unresolved = assessment.get("unresolved_proposition_slots")
        if not isinstance(unresolved, str) or not unresolved:
            raise RuntimeError("natural-quality duplicate unresolved slots missing")
        first = unresolved.split("|", maxsplit=1)[0]
        assessment["unresolved_proposition_slots"] = f"{first}|{first}"
    elif fixture.mutation != "none":
        raise RuntimeError(
            f"unsupported natural-quality payload mutation: {fixture.mutation}"
        )
    return deepcopy(payload)
