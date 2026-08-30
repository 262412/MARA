from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jsonschema import ValidationError, validate
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_evidence_set_constraint,
)
from ktem.reasoning.mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding,
    candidate_required_slots_from_binding,
)
from ktem.reasoning.mara_qasper_semantic_pack import (
    freeze_qasper_canonical_semantic_pack,
    load_qasper_canonical_semantic_pack,
    prepare_qasper_canonical_records,
    qasper_canonical_evidence_plans,
    qasper_canonical_selector_bindings,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)

from scripts.slurm.qasper_natural_semantic_pack_probe_payload import build_probe_result

CONTRACT = "qasper_natural_semantic_pack_probe.v1"
AUDIT_CONTRACT = "qasper_natural_semantic_pack_probe_audit.v1"
_BOUND_STATES = {
    "relation_bound_support",
    "relation_bound_contradiction",
}
_REQUIRED_NO_COHORTS = {
    "auditable_no",
    "closed_world_no",
    "annotation_disagreement",
}
_SIX_SAMPLE_AMBIGUITY_DENOMINATOR = {
    "ambiguous": 2,
    "unambiguous": 4,
}


@dataclass(frozen=True)
class NaturalPackContext:
    bundle: EvidenceBundle
    slots: list[dict[str, Any]]
    frozen: Any
    loaded: Any
    load_reason: str
    binding: dict[str, Any]
    transaction_id: str


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_probe_inputs(path: Path, *, route: str) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL row {line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"invalid JSONL row {line_number}: object required")
        if route and str(row.get("route") or "") != route:
            continue
        identity = str(row.get("example_id") or row.get("question") or "").strip()
        if not identity:
            raise ValueError(f"invalid JSONL row {line_number}: identity missing")
        selected.setdefault(identity, row)
    return list(selected.values())


def probe_prediction(row: dict[str, Any], *, code_sha: str) -> dict[str, Any]:
    question = str(row.get("question") or "").strip()
    route = str(row.get("route") or "").strip()
    example_id = str(row.get("example_id") or "").strip()
    query_plan = _mapping(_mapping(row.get("evidence_metadata")).get("query_plan"))
    items = _mapping(row.get("evidence_bundle")).get("items")
    if not question or not isinstance(items, list) or not query_plan:
        raise ValueError("natural probe input incomplete")
    context = _freeze_natural_pack(
        question,
        route=route,
        example_id=example_id,
        items=items,
        query_plan=query_plan,
        code_sha=code_sha,
    )
    schema_parser = _schema_parser_probe(
        context.bundle,
        question=question,
        binding=context.binding,
        records=context.frozen.records,
        slots=context.slots,
    )
    ambiguity = _ambiguity_observation(row, context.binding)
    canonical_plan_count = int(schema_parser.get("canonical_plan_count") or 0)
    checks = _structural_checks(
        context.bundle,
        binding=context.binding,
        frozen_digest=context.frozen.semantic_pack_digest,
        loaded=context.loaded,
        load_reason=context.load_reason,
        schema_parser=schema_parser,
        canonical_plan_count=canonical_plan_count,
        ambiguity=ambiguity,
    )
    return build_probe_result(
        contract_id=CONTRACT,
        code_sha=code_sha,
        example_id=example_id,
        route=route,
        question=question,
        items=items,
        context=context,
        canonical_plan_count=canonical_plan_count,
        ambiguity=ambiguity,
        schema_parser=schema_parser,
        no_policy_cohorts=_no_policy_cohorts(row, context.binding),
        checks=checks,
    )


def _freeze_natural_pack(
    question: str,
    *,
    route: str,
    example_id: str,
    items: list[Any],
    query_plan: dict[str, Any],
    code_sha: str,
) -> NaturalPackContext:
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="qasper",
        dataset_family="qasper",
        answer_type="boolean",
        question=question,
        query=question,
        query_plan=deepcopy(query_plan),
    )
    bundle = EvidenceBundle(
        route=route or "natural_semantic_pack", items=deepcopy(items)
    )
    slots = required_semantic_proposition_slots(request)
    source_packing = pack_semantic_proposition_evidence(
        request,
        question,
        slots,
        bundle,
        candidate_priority=True,
    )
    records = prepare_qasper_canonical_records(question, source_packing.records)
    transaction_id = (
        "natural-probe:"
        + canonical_digest(
            {
                "code_sha": code_sha,
                "example_id": example_id,
                "route": route,
                "question": question,
                "items": items,
            }
        )[:24]
    )
    binding = candidate_evidence_set_binding(
        records,
        question,
        candidate_transaction_id=transaction_id,
    )
    bound_slots = candidate_required_slots_from_binding(slots, binding)
    frozen = freeze_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        slots=slots,
        source_packing=source_packing,
        records=records,
        candidate_transaction_id=transaction_id,
        candidate_binding=binding,
        candidate_required_slots=bound_slots,
    )
    loaded, load_reason = load_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        candidate_transaction_id=transaction_id,
    )
    return NaturalPackContext(
        bundle=bundle,
        slots=bound_slots,
        frozen=frozen,
        loaded=loaded,
        load_reason=load_reason,
        binding=binding,
        transaction_id=transaction_id,
    )


def _schema_parser_probe(
    bundle: EvidenceBundle,
    *,
    question: str,
    binding: dict[str, Any],
    records: list[dict[str, Any]],
    slots: list[dict[str, Any]],
) -> dict[str, Any]:
    allowed_bindings = qasper_canonical_selector_bindings(records)
    allowed_plans = qasper_canonical_evidence_plans(bundle)
    applicable_slots = tuple(
        str(slot) for slot in binding.get("applicable_slots") or []
    )
    payload, expected_plan_id = _schema_payload(binding)
    response_format = semantic_proposition_response_format(
        list(allowed_bindings),
        [str(slot.get("slot_id") or "") for slot in slots],
        candidate="yes",
        applicable_proposition_slots=applicable_slots,
        allowed_proposition_slot_bindings=allowed_bindings,
        allowed_proposition_evidence_plans=allowed_plans,
    )
    schema_accepted = True
    schema_reason = ""
    try:
        validate(instance=payload, schema=response_format["json_schema"]["schema"])
    except ValidationError as exc:
        schema_accepted = False
        schema_reason = str(exc.message)
    parsed = parse_semantic_proposition_response(
        json.dumps(payload),
        packed=records,
        slot_ids={str(slot.get("slot_id") or "") for slot in slots},
        model="natural-semantic-pack-probe",
        seed=0,
        candidate="yes",
        applicable_proposition_slots=applicable_slots,
        allowed_proposition_slot_bindings=allowed_bindings,
        slot_evidence_refs={
            str(slot.get("slot_id") or ""): tuple(
                str(ref) for ref in slot.get("evidence_refs") or ()
            )
            for slot in slots
            if str(slot.get("slot_id") or "")
        },
        allowed_proposition_evidence_plans=allowed_plans,
    )
    downstream_status = "not_applicable"
    downstream_reason = ""
    if parsed.value is not None and binding.get("binding_state") in _BOUND_STATES:
        constraint = semantic_relation_evidence_set_constraint(
            parsed.value["premises"],
            build_question_proposition(question),
            str(parsed.value["verdict"]),
            auditor_relationship="distinct_model",
        )
        downstream_status = str(constraint.get("status") or "")
        downstream_reason = str(constraint.get("reason") or "")
    return {
        "schema_accepted": schema_accepted,
        "schema_reason": schema_reason,
        "parser_accepted": parsed.value is not None,
        "parser_reason": parsed.failure_reason,
        "expected_plan_id": expected_plan_id,
        "canonical_plan_count": len(allowed_plans or {}),
        "parsed_plan_id": (
            str(parsed.value.get("canonical_evidence_plan_id") or "")
            if parsed.value is not None
            else ""
        ),
        "downstream_status": downstream_status,
        "downstream_reason": downstream_reason,
    }


def _schema_payload(
    binding: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    state = str(binding.get("binding_state") or "")
    if state not in _BOUND_STATES:
        return (
            {
                "candidate_judgment": "unknown",
                "canonical_evidence_plan_id": "",
            },
            "",
        )
    plan_key = (
        "support_plan" if state == "relation_bound_support" else "contradiction_plan"
    )
    plan = _mapping(_mapping(binding.get("canonical_evidence_plan")).get(plan_key))
    return (
        {
            "candidate_judgment": (
                "supported" if state == "relation_bound_support" else "contradicted"
            ),
            "canonical_evidence_plan_id": str(plan.get("plan_id") or ""),
        },
        str(plan.get("plan_id") or ""),
    )


def _structural_checks(
    bundle: EvidenceBundle,
    *,
    binding: dict[str, Any],
    frozen_digest: str,
    loaded: Any,
    load_reason: str,
    schema_parser: dict[str, Any],
    canonical_plan_count: int,
    ambiguity: dict[str, Any],
) -> dict[str, bool]:
    state = str(binding.get("binding_state") or "")
    expected_flags = {
        "relation_bound_support": (True, False, "bound"),
        "relation_bound_contradiction": (False, True, "bound"),
        "ambiguous_conflict": (True, True, "missing"),
        "unresolved": (False, False, "missing"),
    }.get(state)
    flags = (
        bool(binding.get("support")),
        bool(binding.get("explicit_contradiction")),
        str(binding.get("binding_status") or ""),
    )
    plan_id_matches = (
        schema_parser["expected_plan_id"] == schema_parser["parsed_plan_id"]
    )
    downstream_matches = schema_parser["downstream_status"] in {
        "passed",
        "not_applicable",
    }
    stored = _mapping(bundle.metadata.get("qasper_canonical_semantic_pack"))
    return {
        "pack_round_trip": loaded is not None and not load_reason,
        "pack_digest_stable": (
            loaded is not None
            and loaded.semantic_pack_digest == frozen_digest
            and stored.get("semantic_pack_digest") == frozen_digest
        ),
        "candidate_pack_binding_identical": stored.get("proposition_binding")
        == binding,
        "binding_state_consistent": expected_flags is not None
        and flags == expected_flags,
        "schema_accepts": bool(schema_parser["schema_accepted"]),
        "parser_accepts": bool(schema_parser["parser_accepted"]),
        "schema_parser_plan_identical": plan_id_matches,
        "downstream_reuses_plan_predicate": downstream_matches,
        "canonical_plan_audit_valid": _canonical_plan_audit_valid(
            binding,
            schema_parser,
            canonical_plan_count=canonical_plan_count,
        ),
        "unambiguous_zero_plan_rejected": (
            bool(ambiguity.get("ambiguous")) or canonical_plan_count > 0
        ),
    }


def _canonical_plan_audit_valid(
    binding: dict[str, Any],
    schema_parser: dict[str, Any],
    *,
    canonical_plan_count: int,
) -> bool:
    """Require every bound plan to survive the independent relation audit."""

    state = str(binding.get("binding_state") or "")
    if state not in _BOUND_STATES:
        return True
    return (
        canonical_plan_count > 0
        and bool(schema_parser.get("parser_accepted"))
        and schema_parser.get("expected_plan_id") == schema_parser.get("parsed_plan_id")
        and schema_parser.get("downstream_status") == "passed"
    )


def _ambiguity_observation(
    row: dict[str, Any],
    binding: dict[str, Any],
) -> dict[str, Any]:
    diagnostics = _mapping(row.get("qasper_annotation_diagnostics"))
    reasons = _string_list(diagnostics.get("ambiguity_reasons"))
    state = str(binding.get("binding_state") or "")
    ambiguous = bool(diagnostics.get("ambiguous")) or state == "ambiguous_conflict"
    ambiguous = ambiguous or (
        bool(binding.get("support")) and bool(binding.get("explicit_contradiction"))
    )
    if "annotation_answer_disagreement" in reasons:
        ambiguous = True
    return {
        "ambiguous": ambiguous,
        "reasons": reasons,
        "denominator": "ambiguous" if ambiguous else "unambiguous",
    }


def _no_policy_cohorts(
    row: dict[str, Any],
    binding: dict[str, Any],
) -> list[str]:
    cohorts: list[str] = []
    no_semantics = _mapping(binding.get("no_evidence_semantics"))
    if no_semantics.get("classification") in {
        "explicit_negation",
        "role_incompatibility",
        "partial_scope_only",
    }:
        cohorts.append("auditable_no")
    diagnostics = _mapping(row.get("qasper_annotation_diagnostics"))
    annotation_no = _mapping(diagnostics.get("boolean_no_evidence_semantics"))
    if any(
        int(annotation_no.get(key) or 0) > 0
        for key in (
            "explicit_negation",
            "role_incompatibility",
            "partial_scope_only",
        )
    ):
        cohorts.append("auditable_no")
    if int(annotation_no.get("absence_only") or 0) > 0:
        cohorts.append("closed_world_no")
    if "annotation_answer_disagreement" in set(
        diagnostics.get("ambiguity_reasons") or []
    ):
        cohorts.append("annotation_disagreement")
    if binding.get("binding_state") == "ambiguous_conflict":
        cohorts.append("semantic_plan_ambiguity")
    return list(dict.fromkeys(cohorts))


def build_audit(
    predictions: list[dict[str, Any]],
    *,
    code_sha: str,
    input_path: Path,
    expected_count: int,
) -> dict[str, Any]:
    observed_cohorts = {
        cohort for row in predictions for cohort in row.get("no_policy_cohorts") or []
    }
    failed = [row["example_id"] for row in predictions if row["status"] != "passed"]
    ambiguity_denominator = _counts(
        str(_mapping(row.get("ambiguity")).get("denominator") or "unambiguous")
        for row in predictions
    )
    gates = {
        "prediction_count_complete": len(predictions) == expected_count,
        "all_structural_checks_passed": not failed,
        "no_policy_cohort_coverage_complete": _REQUIRED_NO_COHORTS <= observed_cohorts,
        "single_clean_code_identity": bool(code_sha)
        and {str(row.get("code_sha") or "") for row in predictions} == {code_sha},
        "ambiguity_denominator_complete": (
            sum(ambiguity_denominator.values()) == len(predictions)
            and set(ambiguity_denominator) <= {"ambiguous", "unambiguous"}
        ),
        "six_sample_ambiguity_denominator_4_2": (
            expected_count != 6
            or ambiguity_denominator == _SIX_SAMPLE_AMBIGUITY_DENOMINATOR
        ),
    }
    return {
        "contract_id": AUDIT_CONTRACT,
        "status": "passed" if all(gates.values()) else "failed",
        "code_sha": code_sha,
        "source": str(input_path.resolve()),
        "source_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "prediction_count": len(predictions),
        "expected_prediction_count": expected_count,
        "binding_state_counts": _counts(
            str(row.get("binding_state") or "") for row in predictions
        ),
        "no_policy_cohort_counts": _counts(
            cohort
            for row in predictions
            for cohort in row.get("no_policy_cohorts") or []
        ),
        "ambiguity_denominator": ambiguity_denominator,
        "failed_examples": failed,
        "hard_gates": gates,
    }


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return list(dict.fromkeys(str(item) for item in value if str(item)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay natural QASPER retrieval records through the canonical pack."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--route", default="text_rag")
    parser.add_argument("--expected-count", type=int, default=6)
    args = parser.parse_args()

    rows = load_probe_inputs(args.input, route=args.route)
    predictions = [probe_prediction(row, code_sha=args.code_sha) for row in rows]
    audit = build_audit(
        predictions,
        code_sha=args.code_sha,
        input_path=args.input,
        expected_count=args.expected_count,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = args.output_dir / "natural_semantic_pack_predictions.jsonl"
    audit_path = args.output_dir / "natural_semantic_pack_audit.json"
    predictions_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in predictions)
    )
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(f"natural_semantic_pack_status={audit['status']}")
    print(f"natural_semantic_pack_predictions={predictions_path.resolve()}")
    print(f"natural_semantic_pack_audit={audit_path.resolve()}")
    return 0 if audit["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
