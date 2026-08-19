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
    from .answer_abstention import apply_abstention_projection
    from .answer_finalizer import (
        _finalization_answer_source,
        _prepare_finalization_evidence,
        _prepare_standard_answer,
        _record_standard_finalization,
        _store_finalized_answers,
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
    answer_for_scoring, source = select_scoring_answer(
        answer_for_user=answer_for_user,
        answer_for_scoring_source=answer_for_scoring_source,
        structured_answer=structured_answer,
        truncated_answer=truncated_answer,
        dataset_name=dataset_name,
        mode=mode,
        preserve_semantic_answer=preserve_semantic_answer,
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
