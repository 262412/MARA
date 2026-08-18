from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of

VISUAL_EVIDENCE_AUTHORITY_CONTRACT = "visual_evidence_authority.v1"
_NON_ANSWER_MARKERS = (
    "could not retrieve enough evidence",
    "no vlm backend is configured",
    "unable to answer from the visual evidence",
)


def record_visual_answer_authority(
    bundle: Any,
    answer: str,
    *,
    backend: str,
) -> bool:
    """Bind a visual answer to the page identities supplied to the generator."""

    value = str(answer or "").strip()
    if not value or any(marker in value.lower() for marker in _NON_ANSWER_MARKERS):
        return False
    evidence_ids = _page_evidence_ids(bundle)
    if not evidence_ids:
        return False
    metadata = getattr(bundle, "metadata", None)
    if not isinstance(metadata, dict):
        return False
    metadata["visual_answer_authority"] = {
        "contract_id": VISUAL_EVIDENCE_AUTHORITY_CONTRACT,
        "answer": value,
        "evidence_ids": evidence_ids,
        "backend": str(backend or "visual_generator"),
    }
    return True


def validated_visual_answer_authority(
    bundle: Any,
    answer: str,
) -> dict[str, Any] | None:
    """Return a visual authority only when it still matches selected page evidence."""

    metadata = getattr(bundle, "metadata", None)
    authority = (
        metadata.get("visual_answer_authority") if isinstance(metadata, dict) else None
    )
    if not isinstance(authority, dict):
        return None
    if authority.get("contract_id") != VISUAL_EVIDENCE_AUTHORITY_CONTRACT:
        return None
    if str(authority.get("answer") or "").strip() != str(answer or "").strip():
        return None
    selected_ids = set(_page_evidence_ids(bundle))
    evidence_ids = _unique_strings(authority.get("evidence_ids"))
    if not evidence_ids or not set(evidence_ids) <= selected_ids:
        return None
    return {
        **authority,
        "answer": str(authority["answer"]).strip(),
        "evidence_ids": evidence_ids,
    }


def _page_evidence_ids(bundle: Any) -> list[str]:
    output: list[str] = []
    for item in getattr(bundle, "items", []) or []:
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("modality") or item.get("element_type") or "").lower()
            != "page_image"
        ):
            continue
        if str(item.get("evidence_level") or "").lower() != "page":
            continue
        try:
            evidence_id = identity_of(item).key
        except ValueError:
            continue
        if evidence_id and evidence_id not in output:
            output.append(evidence_id)
    metadata = getattr(bundle, "metadata", None)
    requested = (
        metadata.get("visual_generation_evidence_ids")
        if isinstance(metadata, dict)
        else None
    )
    if isinstance(requested, list):
        return [
            evidence_id
            for evidence_id in _unique_strings(requested)
            if evidence_id in output
        ]
    return output


def _unique_strings(values: Any) -> list[str]:
    output: list[str] = []
    for value in values or ():
        normalized = str(value or "").strip()
        if normalized and normalized not in output:
            output.append(normalized)
    return output
