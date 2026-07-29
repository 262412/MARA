from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .metrics import is_abstention_answer


@dataclass(frozen=True)
class AnswerabilityCandidate:
    product_answer: str
    pre_guardrail_answer: str
    pre_verification_answer: str
    candidate_for_answerability: str
    input_candidate_kind: str
    product_abstained: bool
    recovery_attempted: bool


def select_answerability_candidate(
    prediction: dict[str, Any],
) -> AnswerabilityCandidate:
    """Select an existing substantive answer for offline answerability review."""

    product_answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    ).strip()
    metadata_sources = _metadata_sources(prediction)
    pre_guardrail = _first_substantive_value(
        metadata_sources,
        "pre_guardrail_answer",
    )
    pre_verification = _first_substantive_value(
        metadata_sources,
        "pre_verification_answer",
    )
    product_abstained = _structured_abstention(prediction, product_answer)
    if not product_abstained:
        return AnswerabilityCandidate(
            product_answer=product_answer,
            pre_guardrail_answer=pre_guardrail,
            pre_verification_answer=pre_verification,
            candidate_for_answerability=product_answer,
            input_candidate_kind="product_answer",
            product_abstained=False,
            recovery_attempted=False,
        )

    candidate, kind = _original_candidate(pre_guardrail, pre_verification)
    return AnswerabilityCandidate(
        product_answer=product_answer,
        pre_guardrail_answer=pre_guardrail,
        pre_verification_answer=pre_verification,
        candidate_for_answerability=candidate,
        input_candidate_kind=kind,
        product_abstained=True,
        recovery_attempted=bool(candidate),
    )


def _original_candidate(
    pre_guardrail: str,
    pre_verification: str,
) -> tuple[str, str]:
    if pre_guardrail and not is_abstention_answer(pre_guardrail):
        return pre_guardrail, "pre_guardrail_answer"
    if pre_verification and not is_abstention_answer(pre_verification):
        return pre_verification, "pre_verification_answer"
    return "", "missing_original_candidate"


def _structured_abstention(
    prediction: dict[str, Any],
    product_answer: str,
) -> bool:
    if is_abstention_answer(product_answer):
        return True
    for source in (prediction, *_metadata_sources(prediction)):
        for key in ("guardrail_decision", "controller_decision"):
            decision = source.get(key)
            if not isinstance(decision, dict):
                continue
            action = str(decision.get("action") or "").strip().lower()
            if action == "abstain":
                return True
        if str(source.get("guardrail_action") or "").strip().lower() == "abstain":
            return True
        if str(source.get("controller_action") or "").strip().lower() == "abstain":
            return True
    return False


def _metadata_sources(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, dict):
        sources.append(metadata)
    bundle = prediction.get("evidence_bundle")
    bundle_metadata = bundle.get("metadata") if isinstance(bundle, dict) else None
    if isinstance(bundle_metadata, dict):
        sources.append(bundle_metadata)
    return sources


def _first_substantive_value(
    sources: list[dict[str, Any]],
    key: str,
) -> str:
    for source in sources:
        value = str(source.get(key) or "").strip()
        if value:
            return value
    return ""
