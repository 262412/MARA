from __future__ import annotations

from copy import deepcopy
from typing import Any

from .boolean_authority_derivation import boolean_derivation_contract_status
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
    atoms = exact_boolean_atoms(decision, evidence_bundle, question=question)
    return atoms[0] if atoms else None


def exact_boolean_atoms(
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
) -> list[dict[str, Any]]:
    """Return every independently grounded exact Boolean authority atom."""

    atoms: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    result = next(
        (
            value
            for value in decision.claim_results
            if str(value.get("status") or "") == "supported"
            and str(value.get("authority_status") or "")
            in {"exact", "composite_exact", "semantic_evidence_set"}
        ),
        None,
    )
    if result is None:
        return []
    result_polarity = str(result.get("canonical_answer_polarity") or "")
    decision_polarity = str(decision.canonical_answer_polarity or "")
    if (
        result_polarity not in {"yes", "no"}
        or decision_polarity not in {"yes", "no"}
        or result_polarity != decision_polarity
    ):
        return []
    lookup = unambiguous_evidence_alias_lookup(evidence_bundle.items)
    spans = result.get("supporting_evidence_spans") or ()
    candidates = [value for value in spans if isinstance(value, dict)] or [result]
    for candidate in candidates:
        normalized = _authority_candidate(candidate, result)
        evidence_id = str(
            normalized.get("authoritative_evidence_id")
            or normalized.get("evidence_id")
            or ""
        )
        item = lookup.get(evidence_id)
        if item is None:
            continue
        try:
            canonical_id = identity_of(item).key
        except ValueError:
            continue
        atom = _boolean_atom_fields(normalized, decision, canonical_id)
        if not _boolean_atom_is_complete(atom, item, canonical_id):
            continue
        if _requires_current_paper_actor(question) and atom["actor"] != "current_paper":
            continue
        key = (canonical_id, atom["evidence_ref"])
        if key in seen:
            continue
        seen.add(key)
        source_id, page_label = source_page_locator(item)
        atoms.append(
            {
                **atom,
                "source_id": source_id,
                "page_label": page_label,
                "reason": str(normalized.get("reason") or "exact_boolean_proposition"),
            }
        )
    if str(result.get("authority_status") or "") in {
        "composite_exact",
        "semantic_evidence_set",
    }:
        derivations = bound_boolean_derivations(
            decision,
            atoms,
            question=question,
        )
        if len(derivations) != 1:
            return []
    return atoms


def bound_boolean_derivations(
    decision: VerifyDecision,
    atoms: list[dict[str, Any]],
    *,
    question: str,
) -> list[dict[str, Any]]:
    """Return the selected derivation only after independently binding every leaf."""

    result = next(
        (
            value
            for value in decision.claim_results
            if str(value.get("status") or "") == "supported"
            and str(value.get("authority_status") or "")
            in {"composite_exact", "semantic_evidence_set"}
        ),
        None,
    )
    if result is None:
        return []
    selected_id = str(
        result.get("selected_derivation_id") or decision.selected_derivation_id or ""
    )
    derivations = [
        value
        for value in result.get("authority_derivations") or ()
        if isinstance(value, dict)
        and str(value.get("derivation_id") or "") == selected_id
    ]
    if len(derivations) != 1:
        return []
    selected = derivations[0]
    status = boolean_derivation_contract_status(
        selected,
        atoms,
        question=question,
        canonical_polarity=str(decision.canonical_answer_polarity or ""),
    )
    return [deepcopy(selected)] if status == "bound" else []


def _authority_candidate(
    candidate: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    if candidate is result:
        return result
    return {
        **result,
        "authoritative_evidence_id": candidate.get(
            "evidence_id",
            candidate.get("evidence_identity", ""),
        ),
        "authoritative_evidence_ref": candidate.get(
            "evidence_ref", candidate.get("authoritative_evidence_ref", "")
        ),
        "authoritative_span_id": candidate.get(
            "span_id", candidate.get("authoritative_span_id", "")
        ),
        "authoritative_quote": candidate.get(
            "quote", candidate.get("authoritative_quote", "")
        ),
        "authoritative_span_start": candidate.get(
            "span_start", candidate.get("authoritative_span_start")
        ),
        "authoritative_span_end": candidate.get(
            "span_end", candidate.get("authoritative_span_end")
        ),
        "authoritative_canonical_start": candidate.get(
            "canonical_start", candidate.get("authoritative_canonical_start")
        ),
        "authoritative_canonical_end": candidate.get(
            "canonical_end", candidate.get("authoritative_canonical_end")
        ),
        "actor": candidate.get("actor", result.get("actor", "")),
        "relation": candidate.get(
            "relation", candidate.get("predicate", result.get("relation", ""))
        ),
        "predicate": candidate.get(
            "predicate", candidate.get("relation", result.get("predicate", ""))
        ),
        "object": candidate.get("object", result.get("object", "")),
        "arguments": candidate.get(
            "arguments",
            candidate.get("predicate_arguments", result.get("arguments", ())),
        ),
        "predicate_arguments": candidate.get(
            "predicate_arguments",
            candidate.get("arguments", result.get("predicate_arguments", ())),
        ),
        "polarity": candidate.get(
            "polarity", result.get("canonical_answer_polarity", "")
        ),
        "qualifier": candidate.get("qualifier", result.get("qualifier", "")),
        "quantifier": candidate.get("quantifier", result.get("quantifier", "")),
        "scope": candidate.get(
            "scope", candidate.get("section_scope", result.get("scope", ""))
        ),
        "section_scope": candidate.get(
            "section_scope", candidate.get("scope", result.get("section_scope", ""))
        ),
        "reason": candidate.get("reason", result.get("reason", "")),
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
        "authority_derivations": [],
        "selected_derivation_id": "",
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
