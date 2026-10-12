from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from .evidence_identity import identity_of
from .evidence_schema import EvidenceBundle
from .qasper_layered_answer_relation import (
    answer_clause_has_relation_signal,
    layered_claim_revision_text,
    resolve_qasper_answer_relation_layered,
)
from .typed_proposition_authority_atoms import free_text_claim_result
from .typed_proposition_authority_failure import coherent_authority_failure
from .typed_proposition_authority_schema import missing_authority, verified_authority
from .verification_schema import VerifyDecision

_QueryPlanCommit = Callable[[Any, dict[str, tuple[str, ...]], str], int]


def resolve_layered_free_text_transaction(
    request: Any,
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
    answer: str,
    required_slots: list[Any],
    required_slot_ids: list[str],
    commit_query_plan: _QueryPlanCommit,
) -> VerifyDecision:
    if not required_slots:
        return _missing_required_slot_failure(
            decision,
            question=question,
            answer=answer,
            required_slot_ids=required_slot_ids,
        )

    claims = list(decision.claims) or [str(answer or "").strip()]
    results = list(decision.claim_results)
    failure_reason = _layered_transaction_failure_reason(claims, results)
    if failure_reason:
        return _free_text_authority_failure(
            decision,
            question,
            answer,
            required_slot_ids,
            failure_reason,
        )

    evidence = _resolve_layered_claims(
        claims,
        results,
        decision,
        evidence_bundle,
        question=question,
    )
    if evidence[-1]:
        return _free_text_authority_failure(
            decision,
            question,
            answer,
            required_slot_ids,
            evidence[-1],
        )
    (
        claim_atoms,
        atoms,
        extension_citations,
        unresolved_extensions,
        revision_claims,
        _reason,
    ) = evidence
    extension_claims = _extension_claims_to_remove(
        claims,
        results,
        unresolved_extensions,
        decision,
    )
    return _commit_free_text_transaction(
        request,
        decision,
        question=question,
        answer=answer,
        required_slots=required_slots,
        required_slot_ids=required_slot_ids,
        claim_atoms=claim_atoms,
        atoms=atoms,
        additional_citations=extension_citations,
        unsupported_claims=extension_claims,
        revision_claims=revision_claims,
        reason=(
            "layered_answer_authority_with_pruned_extensions"
            if extension_claims
            else "layered_answer_authority"
        ),
        commit_query_plan=commit_query_plan,
    )


def _missing_required_slot_failure(
    decision: VerifyDecision,
    *,
    question: str,
    answer: str,
    required_slot_ids: list[str],
) -> VerifyDecision:
    authority = missing_authority(
        "free_text",
        question,
        answer,
        required_slot_ids,
        "required_support_slot_missing",
    )
    return coherent_authority_failure(
        decision,
        "required_support_slot_missing",
        typed_authority=authority,
    )


def _resolve_layered_claims(
    claims: list[str],
    results: list[dict[str, Any]],
    decision: VerifyDecision,
    evidence_bundle: EvidenceBundle,
    *,
    question: str,
) -> tuple[
    list[dict[str, Any] | None],
    list[dict[str, Any]],
    list[str],
    list[str],
    list[str],
    str,
]:
    claim_atoms: list[dict[str, Any] | None] = []
    atoms: list[dict[str, Any]] = []
    unresolved_extensions: list[str] = []
    extension_citations: list[str] = []
    revision_claims: list[str] = []
    available_evidence_ids = _available_evidence_ids(evidence_bundle)
    for index, claim in enumerate(claims):
        result = results[index] if index < len(results) else {}
        supporting_ids = _claim_supporting_ids(result)
        relation = resolve_qasper_answer_relation_layered(
            question,
            claim,
            list(evidence_bundle.items),
            allowed_evidence_ids=supporting_ids or None,
        )
        supported_atoms = _supported_relation_atoms(relation, result)
        if (
            supported_atoms
            and index > 0
            and not answer_clause_has_relation_signal(
                question,
                claim,
            )
        ):
            supported_atoms = []
        if supported_atoms:
            claim_atoms.append(supported_atoms[0])
            atoms.extend(supported_atoms)
            revision_claims.append(
                layered_claim_revision_text(question, claim, supported_atoms[0])
            )
            continue
        claim_atoms.append(None)
        if index == 0:
            reason = (
                "claim_extension_unverified"
                if len(claims) > 1
                else str(
                    getattr(relation, "reason", "") or "answer_relation_unresolved"
                )
            )
            return [], [], [], [], [], reason
        if (
            str(result.get("status") or "") == "supported"
            and supporting_ids & available_evidence_ids
        ):
            extension_citations.extend(
                evidence_id
                for evidence_id in supporting_ids
                if evidence_id in available_evidence_ids
            )
            revision_claims.append(claim)
            continue
        unresolved_extensions.append(claim)
    return (
        claim_atoms,
        atoms,
        extension_citations,
        unresolved_extensions,
        revision_claims,
        "",
    )


def _layered_transaction_failure_reason(
    claims: list[str],
    results: list[dict[str, Any]],
) -> str:
    if not claims or not results:
        return "answer_claim_support_missing"
    if any(_claim_is_contradictory(result) for result in results):
        return "answer_claim_contradicted"
    return ""


def _free_text_authority_failure(
    decision: VerifyDecision,
    question: str,
    answer: str,
    required_slot_ids: list[str],
    reason: str,
) -> VerifyDecision:
    authority = missing_authority(
        "free_text",
        question,
        answer,
        required_slot_ids,
        reason,
    )
    return coherent_authority_failure(
        decision,
        reason,
        typed_authority=authority,
    )


def _claim_is_contradictory(result: dict[str, Any]) -> bool:
    return str(result.get("status") or "") in {"contradicted", "conflicting"} or bool(
        result.get("contradicting_evidence_ids")
    )


def _supported_relation_atoms(
    resolution: Any,
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    if getattr(resolution, "state", "") != "verified_support":
        return []
    supporting_ids = _claim_supporting_ids(result)
    return [
        atom
        for atom in getattr(resolution, "atoms", ())
        if isinstance(atom, dict)
        and (
            not supporting_ids
            or str(atom.get("evidence_id") or "").strip() in supporting_ids
        )
    ]


def _claim_supporting_ids(result: dict[str, Any]) -> set[str]:
    return {
        str(value).strip()
        for value in result.get("supporting_evidence_ids") or ()
        if str(value).strip()
    }


def _available_evidence_ids(evidence_bundle: EvidenceBundle) -> set[str]:
    return {
        identity_of(item).key for item in evidence_bundle.items if identity_of(item).key
    }


def _extension_claims_to_remove(
    claims: list[str],
    results: list[dict[str, Any]],
    unresolved_extensions: list[str],
    decision: VerifyDecision,
) -> list[str]:
    output: list[str] = []
    for index, claim in enumerate(claims):
        if index == 0:
            continue
        result = results[index] if index < len(results) else {}
        status = str(result.get("status") or "")
        if claim in unresolved_extensions or status != "supported":
            if claim not in output:
                output.append(claim)
    for claim in (*decision.unsupported_claims, *decision.unknown_claims):
        if claim in claims[1:] and claim not in output:
            output.append(claim)
    return output


def _commit_free_text_transaction(
    request: Any,
    decision: VerifyDecision,
    *,
    question: str,
    answer: str,
    required_slots: list[Any],
    required_slot_ids: list[str],
    claim_atoms: list[dict[str, Any] | None],
    atoms: list[dict[str, Any]],
    additional_citations: list[str],
    unsupported_claims: list[str],
    revision_claims: list[str],
    reason: str,
    commit_query_plan: _QueryPlanCommit,
) -> VerifyDecision:
    atom = atoms[0]
    authority_evidence_ids = tuple(
        dict.fromkeys(str(value["evidence_id"]) for value in atoms)
    )
    evidence_ids = list(dict.fromkeys((*authority_evidence_ids, *additional_citations)))
    bindings = {slot.slot_id: authority_evidence_ids for slot in required_slots}
    state_version = commit_query_plan(request, bindings, "verified_support")
    claims = list(decision.claims) or [str(answer or "").strip()]
    claim_results = _layered_claim_results(
        decision,
        claims,
        claim_atoms,
        bindings,
    )
    authority = verified_authority(
        "free_text",
        question,
        answer,
        claim_results,
        bindings,
        atoms,
        state="verified_support",
        reason=reason,
        query_plan_state_version=state_version,
        required_slot_ids=required_slot_ids,
    )
    revision_candidate = "\n".join(
        claim for claim in revision_claims if str(claim or "").strip()
    )
    if revision_candidate and revision_candidate == answer:
        revision_candidate = ""
    if revision_candidate:
        authority["revision_candidate"] = revision_candidate
    return _replace_layered_decision(
        decision,
        answer=answer,
        claims=claims,
        claim_results=claim_results,
        authority=authority,
        atom=atom,
        bindings=bindings,
        evidence_ids=evidence_ids,
        unsupported_claims=unsupported_claims,
        reason=reason,
        requires_revision=bool(unsupported_claims or revision_candidate),
    )


def _replace_layered_decision(
    decision: VerifyDecision,
    *,
    answer: str,
    claims: list[str],
    claim_results: list[dict[str, Any]],
    authority: dict[str, Any],
    atom: dict[str, Any],
    bindings: dict[str, tuple[str, ...]],
    evidence_ids: list[str],
    unsupported_claims: list[str],
    reason: str,
    requires_revision: bool,
) -> VerifyDecision:
    return replace(
        decision,
        status="supported",
        reason=(
            "Typed QASPER answer authority supports the core claim; "
            "unconfirmed extensions are removed before final verification."
            if unsupported_claims
            else "Typed QASPER answer authority supports the answer."
        ),
        action="revise" if requires_revision else "generate",
        claims=claims,
        unsupported_claims=list(unsupported_claims),
        unknown_claims=list(unsupported_claims),
        verified_citations=evidence_ids,
        claim_results=claim_results,
        authoritative_evidence_id=str(atom["evidence_id"]),
        authoritative_evidence_ref=str(atom["evidence_ref"]),
        authoritative_span_id=str(atom["span_id"]),
        authoritative_quote=str(atom["quote"]),
        authoritative_span_start=atom.get("span_start"),
        authoritative_span_end=atom.get("span_end"),
        authoritative_canonical_start=atom.get("canonical_start"),
        authoritative_canonical_end=atom.get("canonical_end"),
        actor=str(atom["actor"]),
        section_scope=str(atom["section_scope"]),
        relation=str(atom["relation"]),
        object=str(atom["object"]),
        predicate_arguments=tuple(atom.get("arguments") or ()),
        qualifier=str(atom["qualifier"]),
        quantifier=str(atom["quantifier"]),
        verified_support_slot_ids=list(bindings),
        typed_authority=authority,
    )


def _layered_claim_results(
    decision: VerifyDecision,
    claims: list[str],
    claim_atoms: list[dict[str, Any] | None],
    bindings: dict[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        result = (
            decision.claim_results[index] if index < len(decision.claim_results) else {}
        )
        claim_atom = claim_atoms[index] if index < len(claim_atoms) else None
        if claim_atom is None:
            claim_supported = str(result.get("status") or "") == "supported" and bool(
                _claim_supporting_ids(result)
            )
            output.append(
                {
                    **result,
                    "claim_id": str(result.get("claim_id") or f"claim:{index + 1}"),
                    "claim": claim,
                    "authority_status": (
                        "semantic"
                        if claim_supported
                        else str(result.get("authority_status") or "")
                    ),
                    "verified_slot_state": "",
                    "verified_support_slot_ids": [],
                }
            )
            continue
        output.append(
            free_text_claim_result(
                result,
                claim=claim,
                claim_id=f"claim:{index + 1}",
                atom=claim_atom,
                slot_ids=list(bindings),
            )
        )
    return output
