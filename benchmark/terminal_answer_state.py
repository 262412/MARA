from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .metrics import is_abstention_answer

TERMINAL_ANSWER_STATE = "terminal_answer_state.v1"


@dataclass(frozen=True)
class TerminalAnswerState:
    answer: str
    answer_status: str
    verify_decision: dict[str, Any]
    claim_verification: dict[str, Any]
    supporting_evidence: tuple[dict[str, Any], ...]
    guardrail_decision: dict[str, Any]
    emitted_citations: tuple[dict[str, Any], ...]
    state_version: int = 1

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["supporting_evidence"] = list(self.supporting_evidence)
        payload["emitted_citations"] = list(self.emitted_citations)
        return payload


def rebuild_terminal_answer_state(
    prediction: dict[str, Any],
    *,
    answer: str,
    verify_decision: dict[str, Any],
    supporting_evidence: list[dict[str, Any]],
    guardrail_decision: dict[str, Any],
    emitted_citations: list[dict[str, Any]],
    claim_verification: dict[str, Any] | None = None,
    scoring_answer: str | None = None,
) -> dict[str, Any]:
    """Atomically replace every field whose meaning depends on the final answer."""

    terminal_answer = _terminal_answer(answer)
    scored_answer = (
        terminal_answer if scoring_answer is None else _terminal_answer(scoring_answer)
    )
    abstained = is_abstention_answer(terminal_answer)
    answer_status = "abstained" if abstained else "answered"
    decision = dict(verify_decision)
    claims = _claim_verification(decision, claim_verification)
    support = [] if abstained else [dict(item) for item in supporting_evidence]
    citations = [] if abstained else [dict(item) for item in emitted_citations]
    guardrail = dict(guardrail_decision)

    prediction["predicted_answer"] = terminal_answer
    prediction["answer_for_scoring"] = scored_answer
    if not _presentation_matches(prediction.get("answer_for_user"), terminal_answer):
        prediction["answer_for_user"] = terminal_answer
    prediction["answer_status"] = answer_status
    prediction["verify_decision"] = decision
    prediction["claim_verification"] = claims
    prediction["guardrail_decision"] = guardrail
    prediction["structured_citations"] = citations
    prediction["predicted_citations"] = _citation_texts(citations)

    metadata_targets = _metadata_targets(prediction)
    for metadata in metadata_targets:
        metadata["verify_decision"] = decision
        metadata["claim_verification"] = claims
        metadata["guardrail_decision"] = guardrail
        metadata["verified_evidence"] = support
        metadata["verified_claim_support_evidence"] = support
        metadata["emitted_citation_evidence"] = support if citations else []
        metadata["cited_evidence"] = support if citations else []
        metadata["answer_dependent_state"] = TERMINAL_ANSWER_STATE

    post_verification = {
        "contract_id": TERMINAL_ANSWER_STATE,
        "answer": terminal_answer,
        "status": str(decision.get("status") or ""),
        "verify_decision": decision,
    }
    prediction["post_contract_verification"] = post_verification
    terminal = TerminalAnswerState(
        answer=terminal_answer,
        answer_status=answer_status,
        verify_decision=decision,
        claim_verification=claims,
        supporting_evidence=tuple(support),
        guardrail_decision=guardrail,
        emitted_citations=tuple(citations),
    ).as_dict()
    prediction["terminal_answer_state"] = terminal
    return terminal


def _claim_verification(
    decision: dict[str, Any],
    supplied: dict[str, Any] | None,
) -> dict[str, Any]:
    if supplied is not None:
        return dict(supplied)
    return {
        "contract_id": TERMINAL_ANSWER_STATE,
        "status": str(decision.get("status") or ""),
        "claim_results": list(decision.get("claim_results") or []),
        "unsupported_claims": list(decision.get("unsupported_claims") or []),
        "unknown_claims": list(decision.get("unknown_claims") or []),
    }


def _metadata_targets(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = prediction.setdefault("evidence_metadata", {})
    targets = [metadata]
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        bundle_metadata = bundle.setdefault("metadata", {})
        if isinstance(bundle_metadata, dict) and bundle_metadata is not metadata:
            targets.append(bundle_metadata)
    return targets


def _terminal_answer(value: Any) -> str:
    return str(value or "").strip()


def _presentation_matches(value: Any, answer: str) -> bool:
    presentation = str(value or "").strip()
    if not presentation:
        return False
    if presentation == answer:
        return True
    return bool(answer and presentation.startswith(f"{answer} "))


def _citation_texts(citations: list[dict[str, Any]]) -> list[str]:
    output: list[str] = []
    for citation in citations:
        source_id = str(citation.get("source_id") or "").strip()
        page_label = str(citation.get("page_label") or "").strip()
        evidence_id = str(citation.get("evidence_id") or "").strip()
        if source_id and page_label:
            value = f"{source_id}#page:{page_label}"
        elif source_id:
            value = f"{source_id}#source"
        elif evidence_id:
            value = f"{evidence_id}#evidence:{evidence_id}"
        else:
            continue
        if value not in output:
            output.append(value)
    return output
