from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

AUDIT_CONTRACT = "qasper_natural_semantic_pack_probe_audit.v1"
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
    runtime_code_sha: str = "",
    runtime_worktree_clean: bool | None = None,
) -> dict[str, Any]:
    causal_replay_observations = _causal_replay_observations(predictions)
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
        "online_local_causal_prefix_matched": bool(predictions)
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
        "causal_transaction_replay_audit": {
            "contract_id": "qasper_natural_causal_replay_audit.v1",
            "hard_rule": "stop_at_first_divergence",
            "observations": causal_replay_observations,
        },
        "hard_gates": gates,
    }


def _causal_replay_observations(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    observations = []
    for prediction in predictions:
        replay = _mapping(prediction.get("causal_transaction_replay"))
        comparison = _mapping(replay.get("comparison"))
        observations.append(
            {
                "example_id": str(prediction.get("example_id") or ""),
                "route": str(prediction.get("route") or ""),
                "status": str(replay.get("status") or "missing"),
                "compared_stage_count": int(
                    comparison.get("compared_stage_count") or 0
                ),
                "first_divergence": dict(_mapping(comparison.get("first_divergence"))),
                "later_stages_evaluated": comparison.get("later_stages_evaluated"),
            }
        )
    return observations


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
