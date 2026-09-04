from __future__ import annotations

from typing import Any


def normalized_answerability_trace(
    prediction: dict[str, Any],
) -> dict[str, Any]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    explicit = metadata.get("answerability_contract_trace")
    if isinstance(explicit, dict):
        return dict(explicit)

    pre = prediction.get("pre_contract_verification")
    post = prediction.get("post_contract_verification")
    if not isinstance(pre, dict) or not isinstance(post, dict):
        return {}
    pre_answer = str(pre.get("answer") or "").strip()
    if not pre_answer:
        decision = pre.get("verify_decision")
        if isinstance(decision, dict):
            pre_answer = " ".join(
                str(claim).strip()
                for claim in decision.get("claims") or []
                if str(claim).strip()
            )
    post_answer = str(
        post.get("answer")
        or prediction.get("answer_for_scoring")
        or prediction.get("predicted_answer")
        or ""
    ).strip()
    if not pre_answer or not post_answer:
        return {}
    qasper = metadata.get("qasper_answerability")
    qasper_trace = dict(qasper) if isinstance(qasper, dict) else {}
    return {
        "pre_contract_answer": pre_answer,
        "post_contract_answer": post_answer,
        "rewrite_applied": _normalized(pre_answer) != _normalized(post_answer),
        "rewrite_type": "legacy_artifact_migration",
        "rewrite_reason": str(
            qasper_trace.get("reason")
            or qasper_trace.get("action")
            or "pre_post_verification_answers_differ"
        ),
        "pre_contract_verification": dict(pre),
        "post_contract_verification": dict(post),
        "trace_source": "legacy_pre_post_verification",
    }


def _normalized(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())
