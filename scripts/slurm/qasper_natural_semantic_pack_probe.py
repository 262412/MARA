from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle

from benchmark.fusion_stage_contract import fusion_stage_audit
from benchmark.qasper_causal_evidence_chain import (
    qasper_causal_evidence_chain_prefix_complete,
)
from scripts.slurm.qasper_natural_causal_transaction import (
    causal_replay_run_context,
    natural_causal_transaction_replay,
)
from scripts.slurm.qasper_natural_production_path_probe import (
    fusion_replay_prediction,
    production_authority_probe,
)
from scripts.slurm.qasper_natural_semantic_pack_audit import build_audit
from scripts.slurm.qasper_natural_semantic_pack_audit import (
    runtime_code_identity as _runtime_code_identity,
)
from scripts.slurm.qasper_natural_semantic_pack_probe_payload import build_probe_result
from scripts.slurm.qasper_natural_semantic_pack_replay import (
    candidate_path_replay_complete,
    candidate_replay_context,
    candidate_request_replay_complete,
)
from scripts.slurm.qasper_natural_semantic_pack_runtime import freeze_natural_pack
from scripts.slurm.qasper_natural_semantic_schema_probe import schema_parser_probe

CONTRACT = "qasper_natural_semantic_pack_probe.v1"
_BOUND_STATES = {
    "relation_bound_support",
    "relation_bound_contradiction",
}


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


def load_probe_run_contexts(
    predictions_path: Path,
    rows: list[dict[str, Any]],
    *,
    semantic_debug_path: Path | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    trace_path = semantic_debug_path or predictions_path.with_name(
        "semantic_debug_traces.jsonl"
    )
    if not trace_path.is_file():
        raise ValueError(f"semantic debug trace missing: {trace_path}")
    transactions: dict[tuple[str, str], dict[str, Any]] = {}
    for line_number, raw_line in enumerate(
        trace_path.read_text().splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            trace = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid semantic debug JSONL row {line_number}: {exc}"
            ) from exc
        if not isinstance(trace, dict):
            raise ValueError(
                f"invalid semantic debug JSONL row {line_number}: object required"
            )
        key = _prediction_key(trace)
        transaction = _mapping(trace.get("causal_transaction"))
        if not all(key) or not transaction:
            raise ValueError(
                f"invalid semantic debug JSONL row {line_number}: "
                "causal transaction identity missing"
            )
        if key in transactions:
            raise ValueError(f"duplicate semantic debug causal transaction: {key}")
        transactions[key] = transaction
    contexts: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _prediction_key(row)
        reference_transaction = transactions.get(key)
        if reference_transaction is None:
            raise ValueError(f"semantic debug causal transaction missing: {key}")
        contexts[key] = causal_replay_run_context(row, reference_transaction)
    return contexts


def probe_prediction(
    row: dict[str, Any],
    *,
    code_sha: str,
    run_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    question = str(row.get("question") or "").strip()
    route = str(row.get("route") or "").strip()
    example_id = str(row.get("example_id") or "").strip()
    items = _mapping(row.get("evidence_bundle")).get("items")
    if not question or not isinstance(items, list):
        raise ValueError("natural probe input incomplete")
    replay = candidate_replay_context(row)
    if not replay.query_plan:
        raise ValueError("natural probe frozen query plan missing")
    context = freeze_natural_pack(
        question,
        route=route,
        example_id=example_id,
        replay=replay,
        code_sha=code_sha,
    )
    schema_parser = schema_parser_probe(
        context.bundle,
        question=question,
        binding=context.binding,
        records=context.frozen.records,
        slots=context.slots,
    )
    ambiguity = _ambiguity_observation(row, context.binding)
    causal_transaction_replay = natural_causal_transaction_replay(
        row,
        context,
        run_context=run_context,
        preserve_frozen_semantic_projection=True,
    )
    fusion_replay = fusion_replay_prediction(row, context.bundle)
    fusion_stage, _fusion_violations = fusion_stage_audit(fusion_replay)
    production_path = production_authority_probe(
        row,
        context,
        question=question,
        candidate_generation=context.candidate_generation,
    )
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
        canonical_selector_projection=context.canonical_selector_projection,
        candidate_prompt_projection=context.candidate_prompt_projection,
        candidate_generation=context.candidate_generation,
        candidate_path_replay=context.candidate_path_replay,
        causal_transaction_replay=causal_transaction_replay,
        fusion_stage=fusion_stage,
        production_path=production_path,
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
        causal_transaction_replay=causal_transaction_replay,
        fusion_stage=fusion_stage,
        production_path=production_path,
        no_policy_cohorts=_no_policy_cohorts(row, context.binding),
        checks=checks,
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
    canonical_selector_projection: dict[str, Any],
    candidate_prompt_projection: dict[str, Any],
    candidate_generation: dict[str, Any],
    candidate_path_replay: dict[str, Any],
    causal_transaction_replay: dict[str, Any],
    fusion_stage: dict[str, Any],
    production_path: dict[str, Any],
) -> dict[str, bool]:
    state = str(binding.get("binding_state") or "")
    expected = {
        "relation_bound_support": (True, False, "bound"),
        "relation_bound_contradiction": (False, True, "bound"),
        "ambiguous_conflict": (True, True, "missing"),
        "unresolved": (False, False, "missing"),
    }.get(state)
    stored = _mapping(bundle.metadata.get("qasper_canonical_semantic_pack"))
    source = _mapping(stored.get("source_packing_observation"))
    checks = {
        "pack_round_trip": loaded is not None and not load_reason,
        "pack_digest_stable": loaded is not None
        and loaded.semantic_pack_digest == frozen_digest
        and stored.get("semantic_pack_digest") == frozen_digest,
        "candidate_pack_binding_identical": stored.get("proposition_binding")
        == binding,
        "binding_state_consistent": expected is not None
        and (
            bool(binding.get("support")),
            bool(binding.get("explicit_contradiction")),
            str(binding.get("binding_status") or ""),
        )
        == expected,
        "schema_accepts": bool(schema_parser["schema_accepted"]),
        "parser_accepts": bool(schema_parser["parser_accepted"]),
        "schema_parser_plan_identical": schema_parser["expected_plan_id"]
        == schema_parser["parsed_plan_id"],
        "downstream_reuses_plan_predicate": schema_parser["downstream_status"]
        in {"passed", "not_applicable"},
        "canonical_plan_audit_valid": _canonical_plan_audit_valid(
            binding, schema_parser, canonical_plan_count=canonical_plan_count
        ),
        "causal_trace_prefix_complete": qasper_causal_evidence_chain_prefix_complete(
            _causal_trace_prefix(
                stored,
                binding=binding,
                canonical_selector_projection=canonical_selector_projection,
            )
        ),
    }
    checks.update(
        _candidate_replay_checks(
            source_observation=source,
            canonical_selector_projection=canonical_selector_projection,
            candidate_prompt_projection=candidate_prompt_projection,
            candidate_generation=candidate_generation,
            candidate_path_replay=candidate_path_replay,
            causal_transaction_replay=causal_transaction_replay,
        )
    )
    checks.update(
        _production_structural_checks(
            ambiguity=ambiguity,
            canonical_plan_count=canonical_plan_count,
            fusion_stage=fusion_stage,
            production_path=production_path,
        )
    )
    return checks


def _production_structural_checks(
    *,
    ambiguity: dict[str, Any],
    canonical_plan_count: int,
    fusion_stage: dict[str, Any],
    production_path: dict[str, Any],
) -> dict[str, bool]:
    exempt = bool(ambiguity.get("ambiguous"))
    preflight = _mapping(production_path.get("audit_preflight"))
    authority = _mapping(production_path.get("boolean_authority"))
    terminal_authority = _mapping(
        production_path.get("typed_authority_terminal_lineage")
    )
    transaction = _mapping(production_path.get("semantic_transaction"))
    projection = _mapping(production_path.get("frozen_plan_projection"))
    return {
        "fusion_stage_contract": fusion_stage.get("status")
        in {"passed", "not_applicable"},
        "production_audit_preflight_called": exempt
        or (preflight.get("called") is True and preflight.get("status") == "passed"),
        "production_boolean_authority_derived": exempt
        or (
            authority.get("called") is True
            and authority.get("derivation_status") == "bound"
        ),
        "production_typed_authority_derived": exempt
        or (
            terminal_authority.get("called") is True
            and terminal_authority.get("typed_authority_state") == "verified_support"
        ),
        "production_terminal_citation_lineage_closed": exempt
        or terminal_authority.get("citation_terminal_lineage_closed") is True,
        "production_semantic_transaction_completed": exempt
        or transaction.get("status") == "parsed",
        "frozen_plan_projection_valid": exempt or projection.get("status") == "passed",
        "unambiguous_authority_bound": exempt or _authority_is_bound(authority),
        "unambiguous_zero_plan_rejected": exempt or canonical_plan_count > 0,
    }


def _authority_is_bound(authority: Mapping[str, Any]) -> bool:
    return (
        authority.get("status") == "supported"
        and authority.get("canonical_answer_polarity")
        == authority.get("input_answer_polarity")
        and bool(authority.get("supporting_evidence_ids"))
        and int(authority.get("authority_derivation_count") or 0) > 0
        and bool(authority.get("selected_derivation_id"))
        and authority.get("evidence_ids_are_bound") is True
    )


def _candidate_replay_checks(
    *,
    source_observation: dict[str, Any],
    canonical_selector_projection: dict[str, Any],
    candidate_prompt_projection: dict[str, Any],
    candidate_generation: dict[str, Any],
    candidate_path_replay: dict[str, Any],
    causal_transaction_replay: dict[str, Any],
) -> dict[str, bool]:
    return {
        "production_candidate_path_replayed": candidate_path_replay_complete(
            candidate_path_replay,
            _mapping(source_observation.get("source_input_snapshot")),
            candidate_prompt_projection,
            canonical_selector_projection,
        ),
        "candidate_request_input_replayed": candidate_request_replay_complete(
            candidate_generation,
            _mapping(candidate_path_replay.get("online_candidate_request")),
        ),
        "online_local_causal_prefix_matched": (
            causal_transaction_replay.get("status") == "matched"
        ),
    }


def _causal_trace_prefix(
    stored_pack: dict[str, Any],
    *,
    binding: dict[str, Any],
    canonical_selector_projection: dict[str, Any],
) -> dict[str, Any]:
    return {
        "main_candidate_generator": {
            "canonical_selector_projection_trace": canonical_selector_projection,
        },
        "semantic_verifier": {
            "semantic_data_lineage": {
                "source_packing": _mapping(
                    stored_pack.get("source_packing_observation")
                ),
                "plan_construction": _mapping(binding.get("plan_construction_trace")),
            }
        },
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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _prediction_key(value: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(value.get("example_id") or ""),
        str(value.get("route") or ""),
    )


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
    parser.add_argument("--semantic-debug-input", type=Path)
    args = parser.parse_args()

    rows = load_probe_inputs(args.input, route=args.route)
    run_contexts = load_probe_run_contexts(
        args.input,
        rows,
        semantic_debug_path=args.semantic_debug_input,
    )
    predictions = [
        probe_prediction(
            row,
            code_sha=args.code_sha,
            run_context=run_contexts[_prediction_key(row)],
        )
        for row in rows
    ]
    runtime_code_sha, runtime_worktree_clean = _runtime_code_identity()
    audit = build_audit(
        predictions,
        code_sha=args.code_sha,
        input_path=args.input,
        expected_count=args.expected_count,
        runtime_code_sha=runtime_code_sha,
        runtime_worktree_clean=runtime_worktree_clean,
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
