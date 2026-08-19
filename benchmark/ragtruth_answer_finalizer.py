from __future__ import annotations

from typing import Any

from .ragtruth_answer_contract import ragtruth_json_answer


def finalize_ragtruth_if_requested(
    raw_answer: str,
    dataset_name: str | None,
) -> str:
    """Normalize a RAGTruth answer before the shared finalization pipeline.

    Non-RAGTruth answers pass through unchanged.  A RAGTruth answer is reduced
    to the strict JSON contract, or to an empty string when that contract
    cannot be produced.  Final answer fields and terminal projection remain
    the responsibility of the public finalizer.
    """

    if "ragtruth" not in str(dataset_name or "").strip().lower():
        return raw_answer
    json_answer, _, _ = ragtruth_json_answer(raw_answer)
    return json_answer


def finalize_ragtruth_prediction(
    prediction: dict[str, Any],
    *,
    raw_answer: str,
    dataset_name: str,
    mode: str,
    presentation_answer: str,
    preserve_semantic_answer: bool,
) -> None:
    """Run shared terminal stages while keeping the RAGTruth JSON exact."""

    from .answer_abstention import apply_abstention_projection
    from .answer_finalizer import (
        _citation_texts,
        _prepare_finalization_evidence,
        _record_standard_finalization,
        _store_finalized_answers,
        attach_structured_citations_from_evidence,
    )
    from .finance_answer_finalization import metadata_citations_allowed
    from .ragtruth_answer_contract import ragtruth_finalization_metadata

    repair_metadata = ragtruth_finalization_metadata(raw_answer)
    normalized_answer = finalize_ragtruth_if_requested(raw_answer, dataset_name)
    _prepare_finalization_evidence(prediction, dataset_name=dataset_name)
    if metadata_citations_allowed(dataset_name, prediction):
        citations = attach_structured_citations_from_evidence(
            prediction,
            span=normalized_answer,
        )
        if citations:
            prediction["structured_citations"] = citations
            prediction["predicted_citations"] = _citation_texts(citations)
    source = "ragtruth_contract" if normalized_answer else "ragtruth_contract_error"
    answer_for_user, answer_for_scoring, source = apply_abstention_projection(
        prediction,
        answer_for_user=normalized_answer,
        answer_for_scoring=normalized_answer,
        answer_text_for_user=normalized_answer,
        presentation_answer=presentation_answer,
        source=source,
        preserve_semantic_answer=preserve_semantic_answer,
    )
    _store_finalized_answers(
        prediction,
        answer_for_user=answer_for_user,
        answer_for_scoring=answer_for_scoring,
        answer_text_for_user=normalized_answer,
        dataset_name=dataset_name,
        mode=mode,
        source=source,
    )
    prediction["answer_finalization"].update(repair_metadata)
    _record_standard_finalization(
        prediction,
        raw_answer=normalized_answer,
        answer_text_for_user=normalized_answer,
        dataset_name=dataset_name,
        qasper_contract_normalized=False,
    )
