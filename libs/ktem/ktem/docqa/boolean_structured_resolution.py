from __future__ import annotations

from .boolean_structured_attributes import (
    _best_system_resolutions,
    _custom_nlu_resolutions,
    _dataset_challenge_resolutions,
    _derogatory_label_analysis_resolutions,
    _downside_resolutions,
    _qualitative_comparison_resolutions,
    _specific_image_domain_resolutions,
    _supervision_resolutions,
)
from .boolean_structured_collections import (
    _balanced_distribution_resolutions,
    _english_experiment_resolutions,
    _external_collection_resolutions,
    _independent_decoder_resolutions,
    _named_membership_resolutions,
    _shared_lexicon_resolutions,
)
from .boolean_structured_schema import StructuredBooleanResolution


def structured_boolean_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    """Resolve Boolean claims only from explicitly closed local structures."""

    candidates = (
        *_named_membership_resolutions(question, text),
        *_balanced_distribution_resolutions(question, text),
        *_independent_decoder_resolutions(question, text),
        *_external_collection_resolutions(question, text),
        *_english_experiment_resolutions(question, text),
        *_downside_resolutions(question, text),
        *_specific_image_domain_resolutions(question, text),
        *_best_system_resolutions(question, text),
        *_dataset_challenge_resolutions(question, text),
        *_supervision_resolutions(question, text),
        *_shared_lexicon_resolutions(question, text),
        *_custom_nlu_resolutions(question, text),
        *_qualitative_comparison_resolutions(question, text),
        *_derogatory_label_analysis_resolutions(question, text),
    )
    return tuple(
        sorted(
            set(candidates),
            key=lambda value: (
                value.polarity,
                len(value.quote),
                value.quote,
                value.reason,
            ),
        )
    )
