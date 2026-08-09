from __future__ import annotations

from typing import Any

from .qasper_answerability_prompts import boolean_answerability_prompt
from .qasper_prompt_budget import fit_qasper_verifier_items


def fit_boolean_verifier_prompt(
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    candidate_answer: str,
    required_evidence_ids: list[str] | None,
    required_slot_ids: list[str] | None,
    priority_evidence_ids: list[str] | None,
    claim_support_evidence_ids: list[str] | None,
    claim_contradiction_evidence_ids: list[str] | None,
    missing_required_slot_ids: list[str] | None = None,
    missing_required_evidence_ids: list[str] | None = None,
) -> tuple[str, str, dict[str, str]]:
    def prompt_builder(bounded_evidence: str) -> str:
        return boolean_answerability_prompt(
            question=question,
            evidence=bounded_evidence,
        )

    if evidence_items is None:
        evidence_items = [
            {
                "evidence_id": "raw-evidence",
                "source_id": "raw-evidence",
                "evaluation_source_id": "raw-evidence",
                "document_id": "raw-evidence",
                "text": evidence,
            }
        ]
    return fit_qasper_verifier_items(
        evidence_items,
        prompt_builder,
        question=question,
        # The generator candidate is advisory for Boolean questions.  Keeping it
        # out of evidence packing makes the verifier input a pure function of the
        # canonical question, evidence, and explicit evidence identities.
        candidate_answer="",
        required_evidence_ids=required_evidence_ids,
        required_slot_ids=required_slot_ids,
        missing_required_slot_ids=missing_required_slot_ids,
        missing_required_evidence_ids=missing_required_evidence_ids,
        priority_evidence_ids=priority_evidence_ids,
        claim_support_evidence_ids=claim_support_evidence_ids,
        claim_contradiction_evidence_ids=claim_contradiction_evidence_ids,
    )
