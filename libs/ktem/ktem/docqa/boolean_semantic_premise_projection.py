from __future__ import annotations

from typing import Any

from .boolean_authority_derivation_support import _strings
from .semantic_relation_clause_validation import (
    frozen_semantic_relation_analyses,
    semantic_relation_clause_analysis,
    semantic_slot_evidence_projection,
    validated_argument_tokens,
)


def semantic_premise_projection(
    index: int,
    contribution: dict[str, Any],
    atom: dict[str, Any],
    *,
    conclusion: dict[str, Any],
    canonical_bindings: dict[str, str],
    applicable_slots: set[str],
    evidence_relation: str,
    question: str,
    proposition: Any,
    required: list[str],
    canonical_plan_projection: Any | None = None,
) -> tuple[dict[str, Any] | None, str]:
    slot_ids = set(_strings(contribution.get("supports_slot_ids")))
    declared_slots = _strings(contribution.get("binds_proposition_slots"))
    proposition_slots = set(declared_slots)
    bindings = dict(contribution.get("proposition_slot_bindings") or {})
    expected = _expected_premise_bindings(
        atom,
        proposition_slots,
        canonical_bindings,
        canonical_plan_projection=canonical_plan_projection,
    )
    fragment = str(contribution.get("proposition_fragment") or "").strip()
    semantics = _premise_semantics(
        atom,
        contribution,
        declared_slots,
        bindings,
        evidence_relation=evidence_relation,
        question=question,
        proposition=proposition,
        required=required,
        canonical_plan_projection=canonical_plan_projection,
    )
    analysis, slot_evidence, tokens, local_relation = semantics
    if not _premise_projection_valid(
        index,
        contribution,
        atom,
        conclusion=conclusion,
        slot_ids=slot_ids,
        proposition_slots=proposition_slots,
        applicable_slots=applicable_slots,
        expected_bindings=expected,
        fragment=fragment,
        evidence_relation=evidence_relation,
        expected_argument_tokens=tokens,
        expected_slot_evidence=slot_evidence,
        expected_local_relation=local_relation,
        local_analysis=analysis,
    ):
        return None, "semantic_premise_projection_mismatch"
    return (
        _premise_projection_payload(
            contribution,
            atom,
            slot_ids=slot_ids,
            proposition_slots=proposition_slots,
            fragment=fragment,
            declared_proposition_slots=declared_slots,
            bindings=bindings,
            evidence_relation=evidence_relation,
            expected_slot_evidence=slot_evidence,
        ),
        "",
    )


def _premise_semantics(
    atom: dict[str, Any],
    contribution: dict[str, Any],
    declared_slots: list[str],
    bindings: dict[str, Any],
    *,
    evidence_relation: str,
    question: str,
    proposition: Any,
    required: list[str],
    canonical_plan_projection: Any | None,
) -> tuple[dict[str, Any], dict[str, Any], list[str], dict[str, Any]]:
    if canonical_plan_projection is not None:
        return _frozen_premise_semantics(
            atom,
            contribution,
            canonical_plan_projection,
            evidence_relation=evidence_relation,
        )
    return _expected_premise_semantics(
        atom,
        contribution,
        declared_slots,
        bindings,
        evidence_relation=evidence_relation,
        question=question,
        proposition=proposition,
        required=required,
    )


def _expected_premise_bindings(
    atom: dict[str, Any],
    proposition_slots: set[str],
    canonical_bindings: dict[str, str],
    *,
    canonical_plan_projection: Any | None,
) -> dict[str, Any]:
    if canonical_plan_projection is None:
        return {
            slot: canonical_bindings[slot]
            for slot in proposition_slots
            if slot in canonical_bindings
        }
    frozen = _frozen_premise_for_atom(atom, canonical_plan_projection)
    return dict((frozen or {}).get("proposition_slot_bindings") or {})


def _frozen_premise_for_atom(
    atom: dict[str, Any], projection: Any
) -> dict[str, Any] | None:
    return next(
        (
            premise
            for premise in projection.premises
            if premise.get("evidence_id") == atom.get("evidence_id")
            and premise.get("span_start") == atom.get("span_start")
            and premise.get("span_end") == atom.get("span_end")
        ),
        None,
    )


def _premise_projection_valid(
    index: int,
    contribution: dict[str, Any],
    atom: dict[str, Any],
    *,
    conclusion: dict[str, Any],
    slot_ids: set[str],
    proposition_slots: set[str],
    applicable_slots: set[str],
    expected_bindings: dict[str, Any],
    fragment: str,
    evidence_relation: str,
    expected_argument_tokens: list[str],
    expected_slot_evidence: dict[str, Any],
    expected_local_relation: dict[str, Any],
    local_analysis: dict[str, Any],
) -> bool:
    bindings = dict(contribution.get("proposition_slot_bindings") or {})
    return not bool(
        contribution.get("role") != f"semantic_premise:{index}"
        or int(contribution.get("order") or 0) != index
        or str(atom.get("relation") or atom.get("predicate") or "")
        != "semantic_premise"
        or not fragment
        or str(atom.get("object") or "") != fragment
        or str(atom.get("polarity") or "") != str(conclusion.get("polarity") or "")
        or str(atom.get("reason") or "") != "semantic_evidence_set_premise"
        or not slot_ids
        or not proposition_slots
        or not proposition_slots <= applicable_slots
        or bindings != expected_bindings
        or dict(atom.get("proposition_slot_bindings") or {}) != expected_bindings
        or contribution.get("evidence_relation") != evidence_relation
        or atom.get("evidence_relation") != evidence_relation
        or contribution.get("argument_tokens") != expected_argument_tokens
        or contribution.get("proposition_slot_evidence") != expected_slot_evidence
        or contribution.get("local_semantic_relation") != expected_local_relation
        or local_analysis.get("joint_relation_clause_bound") is not True
    )


def _premise_projection_payload(
    contribution: dict[str, Any],
    atom: dict[str, Any],
    *,
    slot_ids: set[str],
    proposition_slots: set[str],
    fragment: str,
    declared_proposition_slots: list[str],
    bindings: dict[str, Any],
    evidence_relation: str,
    expected_slot_evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "reference": str(contribution.get("evidence_ref") or ""),
        "supported_slots": slot_ids,
        "proposition_slots": proposition_slots,
        "normalized_fragment": " ".join(fragment.casefold().split()),
        "slot_evidence": expected_slot_evidence,
        "audit_premise": {
            "evidence_id": str(atom.get("evidence_id") or ""),
            "quote": str(atom.get("quote") or ""),
            "proposition_fragment": fragment,
            "supports_slot_ids": sorted(slot_ids),
            "binds_proposition_slots": declared_proposition_slots,
            "proposition_slot_bindings": bindings,
            "evidence_relation": evidence_relation,
        },
    }


def _expected_premise_semantics(
    atom: dict[str, Any],
    contribution: dict[str, Any],
    declared_slots: list[str],
    bindings: dict[str, Any],
    *,
    evidence_relation: str,
    question: str,
    proposition: Any,
    required: list[str],
) -> tuple[dict[str, Any], dict[str, Any], list[str], dict[str, Any]]:
    analysis = semantic_relation_clause_analysis(
        {
            "quote": str(atom.get("quote") or ""),
            "binds_proposition_slots": declared_slots,
            "proposition_slot_bindings": bindings,
            "evidence_relation": evidence_relation,
        },
        proposition,
    )
    span_base = (
        int(atom["canonical_start"])
        if atom.get("canonical_start") is not None
        else int(atom.get("span_start") or 0)
    )
    slot_evidence = semantic_slot_evidence_projection(
        analysis,
        premise_ref=str(contribution.get("evidence_ref") or ""),
        span_base=span_base,
    )
    tokens = list(validated_argument_tokens(question, analysis, required))
    relation = {
        "contract_id": analysis["contract_id"],
        "status": analysis["status"],
        "evidence_relation": analysis["evidence_relation"],
        "joint_relation_clause_bound": analysis["joint_relation_clause_bound"],
        "analysis_digest": analysis["analysis_digest"],
    }
    return analysis, slot_evidence, tokens, relation


def _frozen_premise_semantics(
    atom: dict[str, Any],
    contribution: dict[str, Any],
    projection: Any,
    *,
    evidence_relation: str,
) -> tuple[dict[str, Any], dict[str, Any], list[str], dict[str, Any]]:
    frozen = _frozen_premise_for_atom(atom, projection)
    if frozen is None:
        return {}, {}, [], {}
    selector = str(frozen.get("span_selector") or "")
    analyses = frozen_semantic_relation_analyses(projection, evidence_relation)
    frozen_index = next(
        (
            index
            for index, premise in enumerate(projection.premises)
            if premise is frozen
        ),
        -1,
    )
    analysis = analyses[frozen_index] if 0 <= frozen_index < len(analyses) else {}
    authority_ref = str(contribution.get("evidence_ref") or "")
    slot_evidence = {
        slot: {
            **dict(span),
            "evidence_ref": (
                f"{authority_ref}#slot:{slot}:{span.get('span_start')}:{span.get('span_end')}"
            ),
        }
        for slot, span in projection.slot_evidence.get(selector, {}).items()
    }
    relation = {
        "contract_id": analysis.get("contract_id"),
        "status": analysis.get("status"),
        "evidence_relation": analysis.get("evidence_relation"),
        "joint_relation_clause_bound": analysis.get("joint_relation_clause_bound"),
        "analysis_digest": analysis.get("analysis_digest"),
    }
    return (
        analysis,
        slot_evidence,
        list(projection.covered_tokens_by_ref.get(selector, ())),
        relation,
    )
