from __future__ import annotations

from typing import Any


def finalize_standard_prediction(
    prediction: dict[str, Any],
    *,
    raw_answer: str,
    dataset_name: str,
    mode: str,
    presentation_answer: str,
    preserve_semantic_answer: bool,
) -> None:
    from .answer_finalizer import (
        _finalization_answer_source,
        _prepare_finalization_evidence,
        _prepare_standard_answer,
    )
    from .answer_scoring_adapter import select_scoring_answer
    from .qasper_answer_normalization import normalize_qasper_contract_answer

    raw_answer, repetition_removed, repetition_kind = _finalization_answer_source(
        raw_answer,
        prediction=prediction,
        dataset_name=dataset_name,
        preserve_semantic_answer=preserve_semantic_answer,
    )
    raw_answer, qasper_contract_normalized = normalize_qasper_contract_answer(
        raw_answer,
        prediction=prediction,
        dataset_name=dataset_name,
    )
    _prepare_finalization_evidence(prediction, dataset_name=dataset_name)
    alce_projected = _project_alce_support(prediction, raw_answer)
    (
        answer_for_user,
        answer_text_for_user,
        answer_for_scoring_source,
        structured_answer,
        truncated_answer,
    ) = _prepare_standard_answer(
        raw_answer,
        prediction=prediction,
        dataset_name=dataset_name,
        mode=mode,
    )
    answer_for_user = _attach_alce_structured_citations(
        prediction,
        answer_for_user=answer_for_user,
        answer_text_for_user=answer_text_for_user,
        structured_answer=structured_answer,
        dataset_name=dataset_name,
        mode=mode,
        projected=alce_projected,
    )
    answer_for_scoring, source = select_scoring_answer(
        answer_for_user=answer_for_user,
        answer_for_scoring_source=answer_for_scoring_source,
        structured_answer=structured_answer,
        truncated_answer=truncated_answer,
        dataset_name=dataset_name,
        mode=mode,
        preserve_semantic_answer=preserve_semantic_answer,
    )
    _commit_standard_prediction(
        prediction,
        answer_for_user=answer_for_user,
        answer_for_scoring=answer_for_scoring,
        answer_text_for_user=answer_text_for_user,
        presentation_answer=presentation_answer,
        dataset_name=dataset_name,
        mode=mode,
        source=source,
        raw_answer=raw_answer,
        preserve_semantic_answer=preserve_semantic_answer,
        repetition_removed=repetition_removed,
        repetition_kind=repetition_kind,
        qasper_contract_normalized=qasper_contract_normalized,
    )


def _project_alce_support(
    prediction: dict[str, Any],
    raw_answer: str,
) -> bool:
    from .answer_finalizer import _extract_structured_answer
    from .citation_adapters import project_alce_grounding_support

    structured_answer = _extract_structured_answer(raw_answer)
    return project_alce_grounding_support(
        prediction,
        final_answer=(
            structured_answer["answer"] if structured_answer is not None else raw_answer
        ),
    )


def _commit_standard_prediction(
    prediction: dict[str, Any],
    *,
    answer_for_user: str,
    answer_for_scoring: str,
    answer_text_for_user: str,
    presentation_answer: str,
    dataset_name: str,
    mode: str,
    source: str,
    raw_answer: str,
    preserve_semantic_answer: bool,
    repetition_removed: bool,
    repetition_kind: str,
    qasper_contract_normalized: bool,
) -> None:
    from .answer_abstention import apply_abstention_projection
    from .answer_finalizer import (
        _record_standard_finalization,
        _store_finalized_answers,
    )

    answer_for_user, answer_for_scoring, source = apply_abstention_projection(
        prediction,
        answer_for_user=answer_for_user,
        answer_for_scoring=answer_for_scoring,
        answer_text_for_user=answer_text_for_user,
        presentation_answer=presentation_answer,
        source=source,
        preserve_semantic_answer=preserve_semantic_answer,
    )
    _store_finalized_answers(
        prediction,
        answer_for_user=answer_for_user,
        answer_for_scoring=answer_for_scoring,
        answer_text_for_user=answer_text_for_user,
        dataset_name=dataset_name,
        mode=mode,
        source=source,
        repetition_removed=repetition_removed,
        repetition_kind=repetition_kind,
    )
    _record_standard_finalization(
        prediction,
        raw_answer=raw_answer,
        answer_text_for_user=answer_text_for_user,
        dataset_name=dataset_name,
        qasper_contract_normalized=qasper_contract_normalized,
    )


def _attach_alce_structured_citations(
    prediction: dict[str, Any],
    *,
    answer_for_user: str,
    answer_text_for_user: str,
    structured_answer: dict[str, Any] | None,
    dataset_name: str,
    mode: str,
    projected: bool,
) -> str:
    from .answer_finalizer import (
        _citation_texts,
        _render_structured_answer_for_user,
        attach_structured_citations_from_evidence,
    )
    from .finance_answer_finalization import metadata_citations_allowed

    if not (
        projected
        and structured_answer is not None
        and mode != "product"
        and metadata_citations_allowed(dataset_name, prediction)
    ):
        return answer_for_user
    citations = attach_structured_citations_from_evidence(
        prediction,
        span=answer_text_for_user,
    )
    if not citations:
        return answer_for_user
    prediction["structured_citations"] = citations
    prediction["predicted_citations"] = _citation_texts(citations)
    return _render_structured_answer_for_user(
        {"answer": answer_text_for_user, "citations": citations}
    )
