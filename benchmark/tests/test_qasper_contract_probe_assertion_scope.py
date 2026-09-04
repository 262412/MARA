from __future__ import annotations

from dataclasses import replace

from ktem.reasoning.mara_qasper_semantic_pack import (
    freeze_qasper_canonical_semantic_pack,
    prepare_qasper_canonical_records,
    qasper_canonical_evidence_plans,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)

from scripts.slurm.qasper_debug_contract_probe_cases import (
    _PROBE_CASES,
    _QUESTION,
    _build_request_and_bundle,
)


def test_conditional_statement_has_no_legal_local_support_plan() -> None:
    source = next(case for case in _PROBE_CASES if case.case_id == "auditor_fail")
    case = replace(
        source,
        evidence=(
            "If the authors released the code for the evaluated system, "
            "reproducibility would improve."
        ),
        controlled_fault="",
        proposal_judgment="",
    )
    request, bundle = _build_request_and_bundle(case, 5)
    slots = required_semantic_proposition_slots(request)
    packing = pack_semantic_proposition_evidence(request, _QUESTION, slots, bundle)
    records = prepare_qasper_canonical_records(_QUESTION, packing.records)
    packing = replace(packing, records=records)
    freeze_qasper_canonical_semantic_pack(
        bundle,
        question=_QUESTION,
        slots=slots,
        source_packing=packing,
        records=records,
        candidate_transaction_id="conditional-no-plan-test",
    )

    assert records == []
    assert qasper_canonical_evidence_plans(bundle) == {}
