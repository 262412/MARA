from __future__ import annotations

import hashlib
import json
from typing import Any

from .boolean_authority_derivation_support import (
    _overlapping_premises,
    _records,
    _same_source,
    _strings,
)
from .boolean_authority_schema import (
    ARGUMENT_CONJUNCTION_RULE,
    BOOLEAN_AUTHORITY_DERIVATION_CONTRACT,
    ENTITY_TYPE_JOIN_RULE,
    SEMANTIC_EVIDENCE_SET_RULE,
)
from .boolean_conjunction import boolean_conjunction_spec
from .boolean_proposition_compatibility import boolean_argument_token_coverage
from .boolean_relations import primary_boolean_relation
from .boolean_semantic_derivation_validation import (
    _semantic_evidence_set_status,
    _semantic_header_complete,
)
from .question_proposition import build_question_proposition

COMPOSITE_BOOLEAN_RULES = frozenset(
    {
        ARGUMENT_CONJUNCTION_RULE,
        ENTITY_TYPE_JOIN_RULE,
        SEMANTIC_EVIDENCE_SET_RULE,
    }
)


def boolean_derivation_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "boolean-derivation:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def boolean_derivation_identity_payload(
    *,
    rule_id: str,
    premise_refs: tuple[str, ...] | list[str],
    conclusion: dict[str, Any],
    required_argument_tokens: tuple[str, ...] | list[str],
    bindings: dict[str, Any] | None = None,
    support_mode: str = "",
    verifier_attestation: dict[str, Any] | None = None,
    premise_contributions: (
        tuple[dict[str, Any], ...] | list[dict[str, Any]] | None
    ) = None,
) -> dict[str, Any]:
    """Return the canonical semantic identity of a derivation."""

    payload: dict[str, Any] = {
        "rule_id": str(rule_id or ""),
        "premise_refs": sorted(str(value) for value in premise_refs),
        "conclusion": conclusion,
        "required_argument_tokens": sorted(
            str(value) for value in required_argument_tokens
        ),
        "bindings": {
            str(key): str(value) for key, value in sorted((bindings or {}).items())
        },
    }
    if support_mode:
        payload["support_mode"] = support_mode
    if verifier_attestation:
        payload["verifier_attestation"] = verifier_attestation
    if premise_contributions is not None:
        payload["premise_contributions"] = list(premise_contributions)
    return payload


def boolean_derivation_contract_status(
    derivation: dict[str, Any],
    atoms: list[dict[str, Any]],
    *,
    question: str,
    canonical_polarity: str,
) -> str:
    """Validate one all-premises-required derivation without trusting its producer."""

    header_status, rule_id = _derivation_header_status(derivation)
    if header_status != "bound":
        return header_status
    premise_status, premise_refs, atom_by_ref, contributions = _premise_context(
        derivation,
        atoms,
    )
    if premise_status != "bound":
        return premise_status
    conclusion = derivation.get("conclusion")
    conclusion = conclusion if isinstance(conclusion, dict) else {}
    if not _conclusion_complete(conclusion, canonical_polarity=canonical_polarity):
        return "conclusion_incomplete"
    if not _conclusion_relation_matches(question, conclusion, rule_id=rule_id):
        return "conclusion_relation_mismatch"

    required = _strings(derivation.get("required_argument_tokens"))
    covered = _strings(derivation.get("covered_argument_tokens"))
    if not required or required != covered:
        return "argument_coverage_incomplete"
    identity_status = _derivation_identity_status(
        derivation,
        rule_id=rule_id,
        premise_refs=premise_refs,
        conclusion=conclusion,
        required=required,
        support_mode=str(derivation.get("support_mode") or ""),
        verifier_attestation=(
            derivation.get("verifier_attestation")
            if isinstance(derivation.get("verifier_attestation"), dict)
            else None
        ),
        premise_contributions=(
            contributions if rule_id == SEMANTIC_EVIDENCE_SET_RULE else None
        ),
    )
    if identity_status != "bound":
        return identity_status
    return _rule_contract_status(
        derivation,
        rule_id=rule_id,
        question=question,
        required=required,
        conclusion=conclusion,
        contributions=contributions,
        atom_by_ref=atom_by_ref,
    )


def _derivation_header_status(derivation: dict[str, Any]) -> tuple[str, str]:
    if derivation.get("contract_id") != BOOLEAN_AUTHORITY_DERIVATION_CONTRACT:
        return "contract_mismatch", ""
    rule_id = str(derivation.get("rule_id") or "")
    if rule_id not in COMPOSITE_BOOLEAN_RULES:
        return "rule_unsupported", rule_id
    if (
        derivation.get("premise_mode") != "all_required"
        or derivation.get("semantics") != "open_world"
        or derivation.get("status") != "verified"
    ):
        return "semantics_mismatch", rule_id
    if rule_id == SEMANTIC_EVIDENCE_SET_RULE and not _semantic_header_complete(
        derivation
    ):
        return "semantic_attestation_incomplete", rule_id
    return "bound", rule_id


def _premise_context(
    derivation: dict[str, Any],
    atoms: list[dict[str, Any]],
) -> tuple[str, list[str], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    premise_refs = _strings(derivation.get("premise_refs"))
    premise_ids = _strings(derivation.get("premise_evidence_ids"), unique=False)
    atom_by_ref = {
        str(atom.get("evidence_ref") or ""): atom
        for atom in atoms
        if str(atom.get("evidence_ref") or "")
    }
    contributions = _records(derivation.get("premise_contributions"))
    status = _premise_set_status(
        premise_refs,
        premise_ids,
        atom_by_ref,
        contributions,
        minimum_premises=(
            1
            if str(derivation.get("rule_id") or "") == SEMANTIC_EVIDENCE_SET_RULE
            and str(
                (derivation.get("verifier_attestation") or {}).get("proof_mode") or ""
            )
            == "atomic_semantic"
            else 2
        ),
    )
    return status, premise_refs, atom_by_ref, contributions


def _premise_set_status(
    premise_refs: list[str],
    premise_ids: list[str],
    atom_by_ref: dict[str, dict[str, Any]],
    contributions: list[dict[str, Any]],
    *,
    minimum_premises: int,
) -> str:
    if len(premise_refs) < minimum_premises or len(premise_refs) != len(premise_ids):
        return "premise_set_incomplete"
    if len(set(premise_refs)) != len(premise_refs):
        return "premise_ref_duplicate"
    if set(atom_by_ref) != set(premise_refs):
        return "premise_atom_mismatch"
    if any(
        str(atom_by_ref[ref].get("evidence_id") or "") != evidence_id
        for ref, evidence_id in zip(premise_refs, premise_ids)
    ):
        return "premise_identity_mismatch"
    premise_atoms = [atom_by_ref[ref] for ref in premise_refs]
    if not _same_source(premise_atoms):
        return "cross_source_join"
    if _overlapping_premises(premise_atoms):
        return "premise_span_overlap"
    contribution_by_ref = {
        str(value.get("evidence_ref") or ""): value for value in contributions
    }
    if set(contribution_by_ref) != set(premise_refs) or len(contributions) != len(
        premise_refs
    ):
        return "premise_contribution_mismatch"
    if any(
        str(contribution_by_ref[ref].get("evidence_id") or "")
        != str(atom_by_ref[ref].get("evidence_id") or "")
        for ref in premise_refs
    ):
        return "premise_contribution_identity_mismatch"
    return "bound"


def _derivation_identity_status(
    derivation: dict[str, Any],
    *,
    rule_id: str,
    premise_refs: list[str],
    conclusion: dict[str, Any],
    required: list[str],
    support_mode: str,
    verifier_attestation: dict[str, Any] | None,
    premise_contributions: list[dict[str, Any]] | None,
) -> str:
    bindings = derivation.get("bindings")
    identity_payload = boolean_derivation_identity_payload(
        rule_id=rule_id,
        premise_refs=premise_refs,
        conclusion=conclusion,
        required_argument_tokens=required,
        bindings=bindings if isinstance(bindings, dict) else {},
        support_mode=support_mode,
        verifier_attestation=verifier_attestation,
        premise_contributions=premise_contributions,
    )
    return (
        "bound"
        if str(derivation.get("derivation_id") or "")
        == boolean_derivation_id(identity_payload)
        else "derivation_identity_mismatch"
    )


def _rule_contract_status(
    derivation: dict[str, Any],
    *,
    rule_id: str,
    question: str,
    required: list[str],
    conclusion: dict[str, Any],
    contributions: list[dict[str, Any]],
    atom_by_ref: dict[str, dict[str, Any]],
) -> str:
    if rule_id == ARGUMENT_CONJUNCTION_RULE:
        spec = boolean_conjunction_spec(question)
        if spec is None or required != list(spec["required_argument_tokens"]):
            return "required_argument_mismatch"
        if (
            str(conclusion.get("quantifier") or "") != str(spec["quantifier"])
            or str(conclusion.get("object") or "") != " ".join(required)
            or _strings(conclusion.get("arguments")) != [" ".join(required)]
        ):
            return "conclusion_argument_mismatch"
        return _argument_conjunction_status(
            required,
            contributions,
            atom_by_ref=atom_by_ref,
            question=question,
            conclusion=conclusion,
        )
    if rule_id == SEMANTIC_EVIDENCE_SET_RULE:
        return _semantic_evidence_set_status(
            derivation,
            contributions,
            atom_by_ref=atom_by_ref,
            conclusion=conclusion,
            question=question,
            required=required,
        )
    return (
        "bound"
        if _entity_type_join_complete(
            derivation,
            contributions,
            atom_by_ref=atom_by_ref,
            conclusion=conclusion,
        )
        else "entity_type_binding_incomplete"
    )


def _conclusion_relation_matches(
    question: str,
    conclusion: dict[str, Any],
    *,
    rule_id: str,
) -> bool:
    relation = str(conclusion.get("relation") or conclusion.get("predicate") or "")
    expected = str(primary_boolean_relation(question) or "")
    if rule_id == SEMANTIC_EVIDENCE_SET_RULE:
        typed_expected = build_question_proposition(question).predicate
        return relation == typed_expected
    return relation == expected


def _argument_conjunction_status(
    required: list[str],
    contributions: list[dict[str, Any]],
    *,
    atom_by_ref: dict[str, dict[str, Any]],
    question: str,
    conclusion: dict[str, Any],
) -> str:
    required_set = set(required)
    token_sets = []
    for contribution in contributions:
        reference = str(contribution.get("evidence_ref") or "")
        atom = atom_by_ref[reference]
        reported = set(_strings(contribution.get("argument_tokens")))
        _required, asserted = boolean_argument_token_coverage(
            question,
            str(atom.get("quote") or ""),
        )
        if reported != set(asserted):
            return "premise_argument_projection_mismatch"
        if (
            str(contribution.get("role") or "") != "argument_coverage"
            or str(atom.get("relation") or atom.get("predicate") or "")
            != str(conclusion.get("relation") or conclusion.get("predicate") or "")
            or str(atom.get("polarity") or "") != str(conclusion.get("polarity") or "")
            or str(atom.get("actor") or "") != str(conclusion.get("actor") or "")
        ):
            return "premise_frame_mismatch"
        token_sets.append(reported)
    if any(not tokens or not tokens < required_set for tokens in token_sets):
        return "premise_argument_invalid"
    if set().union(*token_sets) != required_set:
        return "argument_coverage_incomplete"
    if any(
        set().union(
            *(other for offset, other in enumerate(token_sets) if offset != index)
        )
        == required_set
        for index in range(len(token_sets))
    ):
        return "premise_not_required"
    return "bound"


def _entity_type_join_complete(
    derivation: dict[str, Any],
    contributions: list[dict[str, Any]],
    *,
    atom_by_ref: dict[str, dict[str, Any]],
    conclusion: dict[str, Any],
) -> bool:
    bindings = derivation.get("bindings")
    bindings = bindings if isinstance(bindings, dict) else {}
    alias = str(bindings.get("entity_alias") or "").casefold()
    entity_type = str(bindings.get("entity_type") or "").casefold()
    by_role = {
        str(value.get("role") or ""): atom_by_ref[str(value.get("evidence_ref") or "")]
        for value in contributions
    }
    declaration = by_role.get("entity_declaration", {})
    empirical = by_role.get("empirical_relation", {})
    return bool(
        alias
        and entity_type
        and set(by_role) == {"entity_declaration", "empirical_relation"}
        and str(declaration.get("relation") or "") == "type"
        and str(declaration.get("object") or "").casefold() == entity_type
        and alias in str(declaration.get("quote") or "").casefold()
        and str(empirical.get("relation") or "")
        == str(conclusion.get("relation") or "")
        and str(empirical.get("object") or "").casefold() == alias
        and alias in str(empirical.get("quote") or "").casefold()
        and str(conclusion.get("object") or "").casefold() == entity_type
        and _strings(conclusion.get("arguments")) == [entity_type]
    )


def _conclusion_complete(
    conclusion: dict[str, Any],
    *,
    canonical_polarity: str,
) -> bool:
    relation = str(conclusion.get("relation") or conclusion.get("predicate") or "")
    scope = str(conclusion.get("scope") or conclusion.get("section_scope") or "")
    return bool(
        str(conclusion.get("actor") or "") not in {"", "unknown"}
        and relation
        and str(conclusion.get("object") or "")
        and _strings(conclusion.get("arguments"))
        and str(conclusion.get("polarity") or "") == canonical_polarity
        and canonical_polarity in {"yes", "no"}
        and str(conclusion.get("qualifier") or "")
        and str(conclusion.get("quantifier") or "")
        and scope not in {"", "unknown", "future_work"}
    )
