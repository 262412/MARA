from __future__ import annotations

from typing import Any

from ktem.docqa.semantic_relation_clause_validation import (
    premise_slot_evidence_for_audit,
    semantic_relation_evidence_set_constraint,
)

from .mara_semantic_candidate_policy import candidate_bound_semantic_audit_prompt
from .mara_semantic_proposition_stages import audit_stage
from .mara_semantic_transaction_support import semantic_audit_input_identity


def execute_semantic_entailment_audit(
    context: Any,
    value: dict[str, Any],
    conclusion: Any,
) -> tuple[dict[str, Any], Any]:
    """Build exact slot inputs and execute one candidate-bound audit."""

    constraint = semantic_relation_evidence_set_constraint(
        value.get("premises") or [],
        context.proposition,
        str(value.get("verdict") or ""),
        auditor_relationship=context.auditor_relationship,
    )
    slot_evidence = premise_slot_evidence_for_audit(constraint)
    prompt = candidate_bound_semantic_audit_prompt(
        context,
        conclusion,
        value,
        premise_slot_evidence=slot_evidence,
    )
    premises = value.get("premises") or []
    audit = audit_stage(
        context.audit_llm,
        prompt,
        len(premises),
        seed=context.seed + 1,
        premise_slot_expectations={
            f"P{index}": tuple(
                str(slot) for slot in premise.get("binds_proposition_slots") or []
            )
            for index, premise in enumerate(premises, start=1)
            if isinstance(premise, dict)
        },
        premise_slot_evidence=slot_evidence,
        semantic_identity=semantic_audit_input_identity(context, value, conclusion),
    )
    return constraint, audit
