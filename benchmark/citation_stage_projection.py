from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of
from ktem.docqa.evidence_locators import normalized_source_page_locators
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.frozen_canonical_projection_utils import frozen_slot_support_by_ref
from ktem.docqa.frozen_canonical_proposition_projection import (
    frozen_canonical_plan_projection_from_bundle,
)
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)

from .citation_locators import CitationLocator

_UUID_LIKE_SOURCE_RE = re.compile(
    r"^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)

CITATION_STAGE_CONTRACT = "emitted_citation_evidence.v1"
FROZEN_CITATION_PROJECTION_CONTRACT = "frozen_canonical_plan_citation.v1"


def is_uuid_like_source_id(source_id: str) -> bool:
    return bool(_UUID_LIKE_SOURCE_RE.fullmatch(str(source_id or "").strip()))


def source_ref_uses_uuid_like_source(source_ref: str) -> bool:
    source_id = str(source_ref or "").strip().split("#", 1)[0]
    return is_uuid_like_source_id(source_id)


def record_emitted_citation_evidence(
    prediction: dict[str, Any],
    *,
    citations: list[dict[str, str]],
    candidates: list[dict[str, Any]],
    projection_source: str = "explicit_citations",
) -> None:
    cited_items: list[dict[str, Any]] = []
    cited_identities: set[str] = set()
    alias_lookup = unambiguous_evidence_alias_lookup(candidates)
    for raw_citation in citations:
        citation = CitationLocator.from_mapping(raw_citation)
        if citation.kind in {"page", "source"} and not citation.evidence_identity:
            if not _locator_is_present(citation, candidates):
                continue
            page_record = citation.page_evidence_record()
            identity = str(page_record["canonical_id"])
            if identity not in cited_identities:
                cited_identities.add(identity)
                cited_items.append(page_record)
            continue
        for item in candidates:
            if not _citation_matches_item(
                citation,
                item,
                alias_lookup=alias_lookup,
            ):
                continue
            identity = identity_of(item).key
            if identity in cited_identities:
                continue
            cited_identities.add(identity)
            cited_items.append(item)

    evidence_bundle = prediction.get("evidence_bundle")
    metadata_targets: list[dict[str, Any]] = []
    if isinstance(evidence_bundle, dict):
        bundle_metadata = evidence_bundle.get("metadata")
        if isinstance(bundle_metadata, dict):
            metadata_targets.append(bundle_metadata)
    evidence_metadata = prediction.get("evidence_metadata")
    if not isinstance(evidence_metadata, dict):
        evidence_metadata = {}
        prediction["evidence_metadata"] = evidence_metadata
    metadata_targets.append(evidence_metadata)
    for metadata in metadata_targets:
        metadata["emitted_citation_evidence"] = list(cited_items)
        metadata["cited_evidence"] = list(cited_items)
        metadata["citation_stage_contract"] = CITATION_STAGE_CONTRACT
        metadata["citation_stage_trace"] = {
            "contract_id": CITATION_STAGE_CONTRACT,
            "status": "emitted" if cited_items else "empty",
            "projection_source": str(projection_source or "explicit_citations"),
            "input_citation_count": len(citations),
            "candidate_count": len(candidates),
            "emitted_count": len(cited_items),
            "emitted_evidence_identities": [
                identity_of(item).key for item in cited_items
            ],
        }


def citation_trace_projection_fields(
    prediction: Mapping[str, Any],
) -> dict[str, Any]:
    """Expose citation provenance to formal artifacts and causal stages."""

    sources = _citation_metadata_sources(prediction)
    stage_trace = _first_metadata_mapping(sources, "citation_stage_trace")
    frozen_trace = _first_metadata_mapping(
        sources,
        "frozen_citation_projection_trace",
    )
    source = _first_metadata_string(sources, "citation_projection_source")
    emitted = [
        str(value).strip()
        for value in stage_trace.get("emitted_evidence_identities") or []
        if str(value).strip()
    ]
    if not emitted:
        emitted = _emitted_evidence_identities(sources)
    return {
        "citation_stage_trace": deepcopy(stage_trace),
        "frozen_citation_projection_trace": deepcopy(frozen_trace),
        "citation_projection_source": source,
        "emitted_citation_evidence_identities": emitted,
    }


def _first_metadata_mapping(
    sources: list[dict[str, Any]],
    key: str,
) -> dict[str, Any]:
    for metadata in sources:
        value = metadata.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _first_metadata_string(sources: list[dict[str, Any]], key: str) -> str:
    for metadata in sources:
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _emitted_evidence_identities(sources: list[dict[str, Any]]) -> list[str]:
    identities: list[str] = []
    for metadata in sources:
        for item in metadata.get("emitted_citation_evidence") or []:
            if not isinstance(item, dict):
                continue
            try:
                identity = identity_of(item).key
            except (KeyError, TypeError, ValueError):
                continue
            if identity not in identities:
                identities.append(identity)
    return identities


def frozen_canonical_plan_citation_items(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Project citations from one verified, persisted canonical plan.

    The semantic authority trace and canonical pack are both required.  A
    missing, conflicting, or unresolvable premise fails closed instead of
    falling back to the ranked or selected candidate order.
    """

    trace = _frozen_citation_trace()
    metadata_sources = _citation_metadata_sources(prediction)
    authority = _single_verified_authority(metadata_sources)
    if authority is None:
        return [], trace
    plan_id, plan_digest, premise_count = _frozen_plan_identity(authority, trace)
    if not plan_id:
        return [], trace
    projection, reason = _project_frozen_plan(
        prediction,
        candidates,
        metadata_sources,
        plan_id=plan_id,
        plan_digest=plan_digest,
    )
    if projection is None:
        trace["reason"] = reason
        return [], trace
    if len(projection.premises) != premise_count:
        trace["reason"] = "frozen_canonical_plan_premise_count_mismatch"
        return [], trace
    resolved, reason = _resolve_frozen_premises(projection.premises, candidates)
    if not resolved:
        trace["reason"] = reason
        return [], trace
    trace.update(
        status="verified",
        reason="frozen_canonical_plan_projected",
        emitted_premise_count=len(resolved),
        premise_evidence_identities=[identity_of(item).key for item in resolved],
    )
    return resolved, trace


def _frozen_citation_trace() -> dict[str, Any]:
    return {
        "contract_id": FROZEN_CITATION_PROJECTION_CONTRACT,
        "status": "not_applicable",
        "reason": "frozen_canonical_plan_not_present",
        "plan_id": "",
        "plan_digest": "",
        "premise_count": 0,
        "emitted_premise_count": 0,
        "premise_evidence_identities": [],
    }


def _frozen_plan_identity(
    authority: Mapping[str, Any],
    trace: dict[str, Any],
) -> tuple[str, str, int]:
    plan_id = str(authority.get("canonical_evidence_plan_id") or "").strip()
    plan_digest = str(
        authority.get("canonical_plan_digest")
        or authority.get("canonical_evidence_plan_digest")
        or ""
    ).strip()
    premise_count = _non_negative_int(authority.get("premise_count"))
    trace.update(
        status="rejected",
        reason="frozen_canonical_plan_identity_missing",
        plan_id=plan_id,
        plan_digest=plan_digest,
        premise_count=premise_count,
    )
    if not plan_id or not plan_digest or premise_count <= 0:
        return "", "", premise_count
    return plan_id, plan_digest, premise_count


def _project_frozen_plan(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
    metadata_sources: list[dict[str, Any]],
    *,
    plan_id: str,
    plan_digest: str,
) -> tuple[Any | None, str]:
    pack = _single_canonical_pack(metadata_sources)
    if pack is None:
        return None, "frozen_canonical_plan_pack_missing"
    slots = pack.get("slots")
    binding = pack.get("proposition_binding")
    if not isinstance(pack.get("records"), list) or not isinstance(slots, list):
        return None, "frozen_canonical_plan_pack_invalid"
    if not isinstance(binding, Mapping):
        return None, "frozen_canonical_plan_pack_invalid"
    plan = _selected_pack_plan(binding, plan_id)
    if plan is None:
        return None, "frozen_canonical_plan_missing"
    support_by_ref, reason = frozen_slot_support_by_ref(
        plan.get("span_refs") or (),
        slots,
    )
    if reason or support_by_ref is None:
        return None, reason or "frozen_canonical_plan_slot_support_invalid"
    question = str(prediction.get("question") or "").strip()
    proposition = build_question_proposition(question) if question else None
    expected_slots = (
        applicable_proposition_evidence_slots(proposition)
        if proposition is not None
        else None
    )
    bundle = EvidenceBundle(
        route=str(prediction.get("route") or ""),
        items=deepcopy(candidates),
        metadata={"qasper_canonical_semantic_pack": deepcopy(pack)},
    )
    return frozen_canonical_plan_projection_from_bundle(
        bundle,
        plan_id=plan_id,
        proposition=proposition,
        expected_slots=expected_slots,
        expected_plan_digest=plan_digest,
        slot_support_by_ref=support_by_ref,
    )


def _resolve_frozen_premises(
    premises: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    alias_lookup = unambiguous_evidence_alias_lookup(candidates)
    resolved: list[dict[str, Any]] = []
    identities: set[str] = set()
    for premise in premises:
        evidence_id = str(premise.get("evidence_id") or "").strip()
        item = alias_lookup.get(evidence_id)
        if item is None:
            return [], "frozen_canonical_plan_premise_unresolved"
        identity = identity_of(item).key
        if identity not in identities:
            identities.add(identity)
            resolved.append(item)
    return resolved, ""


def _citation_metadata_sources(
    prediction: Mapping[str, Any],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for value in (
        prediction.get("_qasper_causal_replay_metadata"),
        prediction.get("evidence_metadata"),
        _nested_metadata(prediction.get("evidence_bundle")),
        _nested_metadata(prediction.get("engine_terminal_evidence_bundle")),
        _nested_metadata(
            _mapping(prediction.get("engine_terminal_state")).get("evidence_bundle")
        ),
    ):
        if isinstance(value, dict) and all(value is not item for item in sources):
            sources.append(value)
    return sources


def _single_verified_authority(
    metadata_sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    traces = [
        value
        for metadata in metadata_sources
        for value in [metadata.get("semantic_proposition_authority")]
        if isinstance(value, Mapping)
    ]
    if not traces or any(
        str(value.get("status") or "") != "verified" for value in traces
    ):
        return None
    authority = dict(traces[0])
    expected = (
        str(authority.get("canonical_evidence_plan_id") or "").strip(),
        str(
            authority.get("canonical_plan_digest")
            or authority.get("canonical_evidence_plan_digest")
            or ""
        ).strip(),
        _non_negative_int(authority.get("premise_count")),
    )
    if any(
        (
            str(value.get("canonical_evidence_plan_id") or "").strip(),
            str(
                value.get("canonical_plan_digest")
                or value.get("canonical_evidence_plan_digest")
                or ""
            ).strip(),
            _non_negative_int(value.get("premise_count")),
        )
        != expected
        for value in traces[1:]
    ):
        return None
    return authority


def _single_canonical_pack(
    metadata_sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    packs = [
        value
        for metadata in metadata_sources
        for value in [metadata.get("qasper_canonical_semantic_pack")]
        if isinstance(value, Mapping)
    ]
    if not packs:
        return None
    first = dict(packs[0])
    return first if all(dict(value) == first for value in packs[1:]) else None


def _selected_pack_plan(
    binding: Mapping[str, Any],
    plan_id: str,
) -> Mapping[str, Any] | None:
    canonical = binding.get("canonical_evidence_plan")
    if not isinstance(canonical, Mapping):
        return None
    return next(
        (
            candidate
            for candidate in (
                canonical.get("support_plan"),
                canonical.get("contradiction_plan"),
            )
            if isinstance(candidate, Mapping)
            and str(candidate.get("plan_id") or "") == plan_id
        ),
        None,
    )


def _nested_metadata(value: Any) -> dict[str, Any] | None:
    return value.get("metadata") if isinstance(value, dict) else None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _non_negative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return -1
    return parsed if parsed >= 0 else -1


def _citation_matches_item(
    citation: CitationLocator | dict[str, str],
    item: dict[str, Any],
    *,
    alias_lookup: dict[str, dict[str, Any]] | None = None,
) -> bool:
    locator = (
        citation
        if isinstance(citation, CitationLocator)
        else CitationLocator.from_mapping(citation)
    )
    evidence_id = locator.evidence_identity
    citation_source = locator.source_id.strip().lower()
    citation_page = locator.page_label.strip().lower()
    try:
        item_identity = identity_of(item)
    except (KeyError, TypeError, ValueError):
        return False
    if (
        locator.kind
        and locator.kind not in {"page", "source"}
        and locator.kind != item_identity.kind
    ):
        return False
    if evidence_id:
        if alias_lookup is not None:
            matched = alias_lookup.get(evidence_id)
            if matched is None or identity_of(matched) != item_identity:
                return False
        elif evidence_id not in exact_evidence_aliases(item):
            return False
    locators = _item_locators(item)
    if citation_source and citation_page:
        if (citation_source, citation_page) not in locators:
            return False
    elif citation_source and not any(
        source == citation_source for source, _ in locators
    ):
        return False
    elif citation_page and not any(page == citation_page for _, page in locators):
        return False
    if evidence_id and evidence_id != item_identity.key and not citation_source:
        return False
    return bool(evidence_id or citation_source or citation_page)


def _locator_is_present(
    citation: CitationLocator,
    candidates: list[dict[str, Any]],
) -> bool:
    return any(
        (
            not citation.source_id
            or any(
                source == citation.source_id for source, _page in _item_locators(item)
            )
        )
        and (
            not citation.page_label
            or (
                citation.source_id,
                citation.page_label,
            )
            in _item_locators(item)
            or (
                not citation.source_id
                and any(
                    page == citation.page_label
                    for _source, page in _item_locators(item)
                )
            )
        )
        for item in candidates
    )


def _item_locators(item: dict[str, Any]) -> set[tuple[str, str]]:
    return normalized_source_page_locators(item)
