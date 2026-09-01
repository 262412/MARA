from __future__ import annotations

import hashlib
import subprocess
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark.qasper_causal_transaction import (
    QASPER_CAUSAL_TRANSACTION_STAGES,
    compare_qasper_causal_transactions,
)

AUDIT_CONTRACT = "qasper_natural_semantic_pack_probe_audit.v1"
REPLAY_AUDIT_CONTRACT = "qasper_natural_causal_replay_audit.v1"
REPLAY_CONTRACT = "qasper_natural_causal_transaction_replay.v1"
_REQUIRED_NO_COHORTS = {
    "auditable_no",
    "closed_world_no",
    "annotation_disagreement",
}
_SIX_SAMPLE_AMBIGUITY_DENOMINATOR = {
    "ambiguous": 4,
    "unambiguous": 2,
}


def build_audit(
    predictions: list[dict[str, Any]],
    *,
    code_sha: str,
    input_path: Path,
    expected_count: int,
    retrieval_index_binding: Mapping[str, Any],
    runtime_code_sha: str = "",
    runtime_worktree_clean: bool | None = None,
) -> dict[str, Any]:
    causal_replay_observations = _causal_replay_observations(predictions)
    causal_replay_violations = _causal_replay_violations(
        predictions,
        causal_replay_observations,
        expected_count=expected_count,
    )
    causal_replay_audit = _causal_replay_audit(
        causal_replay_observations,
        causal_replay_violations,
        expected_count=expected_count,
    )
    observed_cohorts = {
        cohort for row in predictions for cohort in row.get("no_policy_cohorts") or []
    }
    failed = [row["example_id"] for row in predictions if row["status"] != "passed"]
    ambiguity_denominator = _counts(
        str(_mapping(row.get("ambiguity")).get("denominator") or "unambiguous")
        for row in predictions
    )
    gates = _hard_gates(
        predictions,
        retrieval_index_binding=retrieval_index_binding,
        expected_count=expected_count,
        failed=failed,
        causal_replay_observations=causal_replay_observations,
        causal_replay_violations=causal_replay_violations,
        observed_cohorts=observed_cohorts,
        ambiguity_denominator=ambiguity_denominator,
        code_sha=code_sha,
        runtime_code_sha=runtime_code_sha,
        runtime_worktree_clean=runtime_worktree_clean,
    )
    return {
        "contract_id": AUDIT_CONTRACT,
        "status": "passed" if all(gates.values()) else "failed",
        "code_sha": code_sha,
        "runtime_code_sha": runtime_code_sha,
        "runtime_worktree_clean": runtime_worktree_clean,
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
        "retrieval_index_binding_audit": dict(retrieval_index_binding),
        "causal_transaction_replay_audit": causal_replay_audit,
        "hard_gates": gates,
    }


def _hard_gates(
    predictions: list[dict[str, Any]],
    *,
    retrieval_index_binding: Mapping[str, Any],
    expected_count: int,
    failed: list[str],
    causal_replay_observations: list[dict[str, Any]],
    causal_replay_violations: list[str],
    observed_cohorts: set[str],
    ambiguity_denominator: dict[str, int],
    code_sha: str,
    runtime_code_sha: str,
    runtime_worktree_clean: bool | None,
) -> dict[str, bool]:
    return {
        "real_retrieval_index_artifact_bound": (
            retrieval_index_binding.get("status") == "matched"
            and retrieval_index_binding.get("hard_rule")
            == "stop_at_first_divergence"
            and retrieval_index_binding.get("expected_record_count")
            == expected_count
            and retrieval_index_binding.get("matched_record_count")
            == expected_count
            and not retrieval_index_binding.get("violations")
        ),
        "prediction_count_complete": len(predictions) == expected_count,
        "all_structural_checks_passed": not failed,
        "online_local_causal_prefix_matched": bool(predictions)
        and not causal_replay_violations
        and all(
            observation["status"] == "matched"
            for observation in causal_replay_observations
        ),
        "no_policy_cohort_coverage_complete": _REQUIRED_NO_COHORTS <= observed_cohorts,
        "single_clean_code_identity": _git_sha(code_sha)
        and {str(row.get("code_sha") or "") for row in predictions} == {code_sha}
        and (not runtime_code_sha or runtime_code_sha == code_sha)
        and runtime_worktree_clean is not False,
        "ambiguity_denominator_complete": (
            sum(ambiguity_denominator.values()) == len(predictions)
            and set(ambiguity_denominator) <= {"ambiguous", "unambiguous"}
        ),
        "six_sample_ambiguity_denominator_4_2": (
            expected_count != 6
            or ambiguity_denominator == _SIX_SAMPLE_AMBIGUITY_DENOMINATOR
        ),
    }


def _causal_replay_audit(
    observations: list[dict[str, Any]],
    violations: list[str],
    *,
    expected_count: int,
) -> dict[str, Any]:
    return {
        "contract_id": REPLAY_AUDIT_CONTRACT,
        "replay_contract_id": REPLAY_CONTRACT,
        "hard_rule": "stop_at_first_divergence",
        "expected_observation_count": expected_count,
        "observed_observation_count": len(observations),
        "matched_observation_count": sum(
            observation["status"] == "matched" for observation in observations
        ),
        "observations": observations,
        "violations": violations,
    }


def _causal_replay_observations(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    observations = []
    for prediction in predictions:
        replay = _mapping(prediction.get("causal_transaction_replay"))
        reference = _mapping(replay.get("reference_transaction"))
        local = _mapping(replay.get("local_replay_transaction"))
        computed = compare_qasper_causal_transactions(reference, local)
        expected_status = "matched" if computed.get("status") == "matched" else "failed"
        declared_contract = str(replay.get("contract_id") or "")
        declared_through_stage = replay.get("through_stage_index")
        declared_stage = replay.get("through_stage")
        identity = _prediction_key(prediction)
        identity_ok = (
            _transaction_key(reference) == identity
            and _transaction_key(local) == identity
        )
        valid = bool(
            declared_contract == REPLAY_CONTRACT
            and replay.get("status") == expected_status
            and declared_through_stage == len(QASPER_CAUSAL_TRANSACTION_STAGES)
            and declared_stage == QASPER_CAUSAL_TRANSACTION_STAGES[-1]
            and replay.get("comparison_scope")
            == (f"causal_replay_through_{QASPER_CAUSAL_TRANSACTION_STAGES[-1]}")
            and replay.get("hard_rule") == "stop_at_first_divergence"
            and _declared_comparison_matches(replay, computed)
            and identity_ok
        )
        first_divergence = _first_divergence(computed.get("first_divergence"))
        if not valid and not first_divergence:
            first_divergence = _replay_validation_failure(
                replay,
                identity=identity,
            )
        observations.append(
            {
                "example_id": identity[0],
                "route": identity[1],
                "status": expected_status if valid else "failed",
                "replay_status": str(replay.get("status") or "missing"),
                "replay_contract_id": declared_contract,
                "through_stage_index": declared_through_stage,
                "through_stage": declared_stage,
                "compared_stage_count": int(computed.get("compared_stage_count") or 0),
                "first_divergence": first_divergence,
                "later_stages_evaluated": computed.get("later_stages_evaluated")
                is True,
            }
        )
    return observations


def _causal_replay_violations(
    predictions: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    *,
    expected_count: int,
) -> list[str]:
    keys = [_prediction_key(prediction) for prediction in predictions]
    counts = Counter(keys)
    violations = []
    if len(predictions) != expected_count:
        violations.append(
            "qasper_natural_causal_replay_observation_count_mismatch:"
            f"{len(predictions)}/{expected_count}"
        )
    for key in sorted(counts):
        if not key[0] or not key[1] or counts[key] != 1:
            violations.append(
                "qasper_natural_causal_replay_key_count_mismatch:"
                f"{key[0]}:{key[1]}:{counts[key]}"
            )
    if len(observations) != expected_count:
        violations.append(
            "qasper_natural_causal_replay_observation_count_mismatch:"
            f"{len(observations)}/{expected_count}"
        )
    for observation in observations:
        key = (observation["example_id"], observation["route"])
        if observation["status"] != "matched":
            first = _mapping(observation.get("first_divergence"))
            violations.append(
                "qasper_natural_causal_transaction_replay_failure:"
                f"{key[0]}:{key[1]}:stage_{first.get('stage_index', 0)}:"
                f"{first.get('stage', 'causal_transaction_replay')}:"
                f"{first.get('reason', 'replay_not_matched')}"
            )
    return list(dict.fromkeys(violations))


def _replay_validation_failure(
    replay: Mapping[str, Any],
    *,
    identity: tuple[str, str],
) -> dict[str, Any]:
    if str(replay.get("contract_id") or "") != REPLAY_CONTRACT:
        return {
            "stage_index": 0,
            "stage": "replay_contract",
            "reason": "replay_contract_invalid",
        }
    if replay.get("through_stage_index") != len(QASPER_CAUSAL_TRANSACTION_STAGES):
        return {
            "stage_index": int(replay.get("through_stage_index") or 0),
            "stage": str(replay.get("through_stage") or ""),
            "reason": "replay_not_through_stage12",
        }
    if replay.get("through_stage") != QASPER_CAUSAL_TRANSACTION_STAGES[-1]:
        return {
            "stage_index": len(QASPER_CAUSAL_TRANSACTION_STAGES),
            "stage": str(replay.get("through_stage") or ""),
            "reason": "replay_stage12_identity_mismatch",
        }
    return {
        "stage_index": 0,
        "stage": "transaction_identity",
        "reason": f"replay_transaction_key_mismatch:{identity[0]}:{identity[1]}",
    }


def _declared_comparison_matches(
    replay: Mapping[str, Any],
    computed: Mapping[str, Any],
) -> bool:
    declared = _mapping(replay.get("comparison"))
    return declared.get(
        "contract_id"
    ) == "qasper_causal_transaction_comparison.v1" and declared.get(
        "status"
    ) == computed.get(
        "status"
    )


def _first_divergence(value: Any) -> dict[str, Any]:
    divergence = _mapping(value)
    return {
        key: divergence[key]
        for key in ("stage_index", "stage", "reason")
        if key in divergence
    }


def runtime_code_identity() -> tuple[str, bool]:
    root = Path(__file__).resolve().parents[2]
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return "", False
    return head, not status.strip()


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _git_sha(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 40 and all(
        character in "0123456789abcdef" for character in text
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _prediction_key(value: Mapping[str, Any]) -> tuple[str, str]:
    return str(value.get("example_id") or ""), str(value.get("route") or "")


def _transaction_key(value: Mapping[str, Any]) -> tuple[str, str]:
    return _prediction_key(_mapping(value.get("transaction_key")))
