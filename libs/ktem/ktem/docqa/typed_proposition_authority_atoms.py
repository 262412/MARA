from __future__ import annotations

from copy import deepcopy
from typing import Any

from .boolean_evidence_scope import evidence_item_text
from .evidence_alias_lookup import unambiguous_evidence_alias_lookup
from .evidence_identity import identity_of
from .evidence_schema import EvidenceBundle
from .query_phrase_extraction import source_page_locator
from .typed_proposition_authority_schema import TYPED_PROPOSITION_AUTHORITY_CONTRACT
from .verification_schema import VerifyDecision


def exact_boolean_atom(
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
) -> dict[str, Any] | None:
    result = next(
        (
            value
            for value in decision.claim_results
            if str(value.get("status") or "") == "supported"
            and str(value.get("authority_status") or "") == "exact"
        ),
        None,
    )
    if result is None:
        return None
    result_polarity = str(result.get("canonical_answer_polarity") or "")
    decision_polarity = str(decision.canonical_answer_polarity or "")
    if (
        result_polarity not in {"yes", "no"}
        or decision_polarity not in {"yes", "no"}
        or result_polarity != decision_polarity
    ):
        return None
    lookup = unambiguous_evidence_alias_lookup(evidence_bundle.items)
    evidence_id = str(result.get("authoritative_evidence_id") or "")
    item = lookup.get(evidence_id)
    if item is None:
        return None
    try:
        canonical_id = identity_of(item).key
    except ValueError:
        return None
    atom = _boolean_atom_fields(result, decision, canonical_id)
    if not _boolean_atom_is_complete(atom, item, evidence_id):
        return None
    if _requires_current_paper_actor(question) and atom["actor"] != "current_paper":
        return None
    source_id, page_label = source_page_locator(item)
    return {
        **atom,
        "source_id": source_id,
        "page_label": page_label,
        "reason": "exact_boolean_proposition",
    }


def _boolean_atom_fields(
    result: dict[str, Any],
    decision: VerifyDecision,
    canonical_id: str,
) -> dict[str, Any]:
    relation = str(result.get("relation") or result.get("predicate") or "")
    section_scope = str(result.get("section_scope") or result.get("scope") or "")
    return {
        "evidence_id": canonical_id,
        "evidence_ref": str(result.get("authoritative_evidence_ref") or ""),
        "span_id": str(
            result.get("authoritative_span_id")
            or result.get("authoritative_evidence_ref")
            or ""
        ),
        "quote": str(result.get("authoritative_quote") or ""),
        "span_start": result.get("authoritative_span_start"),
        "span_end": result.get("authoritative_span_end"),
        "canonical_start": result.get("authoritative_canonical_start"),
        "canonical_end": result.get("authoritative_canonical_end"),
        "actor": str(result.get("actor") or ""),
        "relation": relation,
        "predicate": relation,
        "object": str(result.get("object") or ""),
        "arguments": list(
            result.get("arguments") or result.get("predicate_arguments") or []
        ),
        "polarity": str(
            result.get("canonical_answer_polarity")
            or decision.canonical_answer_polarity
        ),
        "qualifier": str(result.get("qualifier") or ""),
        "quantifier": str(result.get("quantifier") or ""),
        "scope": section_scope,
        "section_scope": section_scope,
    }


def _boolean_atom_is_complete(
    atom: dict[str, Any],
    item: dict[str, Any],
    evidence_id: str,
) -> bool:
    start = atom["span_start"]
    end = atom["span_end"]
    return bool(
        atom["evidence_id"] == evidence_id
        and atom["evidence_ref"]
        and atom["evidence_ref"] == atom["span_id"]
        and atom["quote"]
        and isinstance(start, int)
        and isinstance(end, int)
        and 0 <= start < end
        and evidence_item_text(item)[start:end] == atom["quote"]
        and atom["actor"] not in {"", "unknown"}
        and atom["section_scope"] not in {"", "unknown"}
        and atom["relation"]
        and atom["object"]
        and atom["arguments"]
        and atom["qualifier"]
        and atom["quantifier"]
        and atom["polarity"] in {"yes", "no"}
    )


def free_text_claim_result(
    result: dict[str, Any],
    *,
    claim: str,
    claim_id: str,
    atom: dict[str, Any],
    slot_ids: list[str],
) -> dict[str, Any]:
    return {
        **result,
        "claim_id": str(result.get("claim_id") or claim_id),
        "claim": claim,
        "status": "supported",
        "supporting_evidence_ids": [atom["evidence_id"]],
        "contradicting_evidence_ids": [],
        "authority_status": "exact",
        "authoritative_evidence_id": atom["evidence_id"],
        "authoritative_evidence_ref": atom["evidence_ref"],
        "authoritative_span_id": atom["span_id"],
        "authoritative_quote": atom["quote"],
        "authoritative_span_start": atom["span_start"],
        "authoritative_span_end": atom["span_end"],
        "authoritative_canonical_start": atom.get("canonical_start"),
        "authoritative_canonical_end": atom.get("canonical_end"),
        "actor": atom["actor"],
        "section_scope": atom["section_scope"],
        "scope": atom["scope"],
        "relation": atom["relation"],
        "predicate": atom["predicate"],
        "object": atom["object"],
        "arguments": list(atom["arguments"]),
        "predicate_arguments": list(atom["arguments"]),
        "qualifier": atom["qualifier"],
        "quantifier": atom["quantifier"],
        "supporting_evidence_spans": [deepcopy(atom)],
        "contradicting_evidence_spans": [],
        "verified_slot_state": "verified_support",
        "verified_support_slot_ids": list(slot_ids),
        "typed_authority_contract": TYPED_PROPOSITION_AUTHORITY_CONTRACT,
    }


def unknown_claim_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "status": "unknown",
        "supporting_evidence_ids": [],
        "contradicting_evidence_ids": [],
        "authority_status": "missing",
        "authoritative_evidence_id": "",
        "authoritative_evidence_ref": "",
        "authoritative_span_id": "",
        "authoritative_quote": "",
        "authoritative_span_start": None,
        "authoritative_span_end": None,
        "authoritative_canonical_start": None,
        "authoritative_canonical_end": None,
        "actor": "",
        "section_scope": "",
        "scope": "",
        "relation": "",
        "predicate": "",
        "object": "",
        "arguments": [],
        "predicate_arguments": [],
        "qualifier": "",
        "quantifier": "",
        "supporting_evidence_spans": [],
        "contradicting_evidence_spans": [],
        "authoritative_conflict": {},
        "verified_slot_state": "",
        "verified_support_slot_ids": [],
    }


def conflict_slot_bindings(
    slots: list[Any],
    atoms: list[dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    all_ids = tuple(
        dict.fromkeys(
            str(atom.get("evidence_id") or "")
            for atom in atoms
            if str(atom.get("evidence_id") or "")
        )
    )
    output: dict[str, tuple[str, ...]] = {}
    for slot in slots:
        existing = tuple(value for value in slot.evidence_ids if value in all_ids)
        page_label = str(getattr(slot.locator, "page_label", "") or "")
        page_ids = tuple(
            dict.fromkeys(
                str(atom.get("evidence_id") or "")
                for atom in atoms
                if page_label and str(atom.get("page_label") or "") == page_label
            )
        )
        selected = (
            all_ids
            if str(slot.statement_kind or "") == "boolean_proposition"
            else page_ids or existing or all_ids
        )
        if selected:
            output[slot.slot_id] = selected
    return output


def _requires_current_paper_actor(question: str) -> bool:
    lowered = str(question or "").lower()
    return any(
        value in lowered
        for value in (
            "the author",
            "the paper",
            "the study",
            "proposed",
            "this paper",
            "this study",
        )
    )
