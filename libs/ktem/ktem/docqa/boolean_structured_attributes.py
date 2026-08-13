from __future__ import annotations

import re

from .boolean_structured_schema import StructuredBooleanResolution
from .boolean_structured_text import _concept_stems, _sentence_windows


def _downside_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        re.search(r"\b(?:mention|note|identify|discuss|report)\w*\b", lowered_question)
        and re.search(
            r"\b(?:downside|disadvantage|drawback|limitation|negative effect)\b",
            lowered_question,
        )
    ):
        return ()
    target_stems = _concept_stems(question) - {
        "author",
        "disadv",
        "downsi",
        "drawba",
        "identi",
        "limita",
        "mentio",
        "negati",
        "report",
    }
    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=4):
        lowered = window.lower()
        if not target_stems & _concept_stems(window):
            continue
        explicit_downside = re.search(
            r"\b(?:disadvantages?|downsides?|drawbacks?|limitations?)\b|"
            r"\b(?:information|signal|detail|accuracy|score|performance)\b"
            r"[^.!?]{0,100}\b(?:lost|loss|lower|decrease|decreased|decreases|"
            r"decreasing|hurt|harm|worse)\b|"
            r"\b(?:lost|loss|lower|decrease|decreased|decreases|decreasing|hurt|"
            r"harm|worse)\b"
            r"[^.!?]{0,100}\b(?:accuracy|score|performance|information)\b",
            lowered,
        )
        if explicit_downside is None:
            continue
        output.append(
            StructuredBooleanResolution(
                polarity="yes",
                quote=window,
                quantifier="any",
                reason="explicit_target_downside",
            )
        )
    return tuple(output)


def _specific_image_domain_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not re.search(
        r"\bimages?\b[^?]{0,80}\b(?:specific|particular|controlled)\s+domain\b",
        lowered_question,
    ):
        return ()
    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=3):
        lowered = window.lower()
        if re.search(
            r"\b(?:diverse|broad|general-purpose)\s+(?:web\s+)?images?\b", lowered
        ):
            continue
        synthetic_scope = re.search(
            r"\b(?:only\s+on\s+)?synthetic\s+(?:data|datasets?|images?)\b",
            lowered,
        )
        controlled_images = re.search(
            r"\b(?:construct|generate|create)\w*\b[^.!?]{0,100}\bimages?\b"
            r"[^.!?]{0,100}\b(?:controlled|abstract|colored|synthetic)\b|"
            r"\b(?:controlled|abstract|colored|synthetic)\b[^.!?]{0,100}"
            r"\b(?:scenes?|shapes?|images?)\b",
            lowered,
        )
        image_captioning_scope = re.search(
            r"\b(?:image\s+captioning|images?)\b[^.!?]{0,180}"
            r"\bsynthetic\s+datasets?\b[^.!?]{0,100}\bconstruct\w*\b|"
            r"\bconstruct\w*\b[^.!?]{0,100}\bsynthetic\s+datasets?\b"
            r"[^.!?]{0,180}\b(?:image\s+captioning|images?)\b",
            lowered,
        )
        if synthetic_scope and (controlled_images or image_captioning_scope):
            output.append(
                StructuredBooleanResolution(
                    polarity="yes",
                    quote=window,
                    quantifier="only",
                    reason="explicit_specific_synthetic_image_domain",
                )
            )
    return tuple(output)


def _best_system_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    question_match = re.search(
        r"\b(?:does|did|is|was)\s+(?:the\s+)?(?P<system>[A-Za-z][A-Za-z0-9_-]*)"
        r"(?:[- ]based\s+model)?\s+(?:reach|achieve|attain|have|get)\w*\s+"
        r"(?:the\s+)?best\s+performance\b",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    if question_match is None:
        return ()
    system = question_match.group("system").lower()
    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=4):
        lowered = window.lower()
        if not re.search(rf"\b{re.escape(system)}(?:[- ]based)?\b", lowered):
            continue
        behind_winner = re.search(
            r"\b(?:behind|below)\b[^.!?]{0,100}\b(?:winner|winning|best)\b|"
            r"\b(?:second\s+(?:position|place)|rank(?:ed|s)?\s+second)\b|"
            r"\bhas\s+not\s+improved\b[^.!?]{0,120}\b(?:winner|winning|best|scores?)\b",
            lowered,
        )
        if behind_winner:
            output.append(
                StructuredBooleanResolution(
                    polarity="no",
                    quote=window,
                    quantifier="all",
                    reason="explicit_non_winning_system_comparison",
                )
            )
    return tuple(output)


def _dataset_challenge_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        re.search(r"\b(?:challenge|difficulty|noise)\w*\b", lowered_question)
        and re.search(r"\b(?:data|dataset|task)\b", lowered_question)
        and re.search(r"\b(?:establish|exist|present|occur)\w*\b", lowered_question)
    ):
        return ()
    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=3):
        lowered = window.lower()
        if re.search(
            r"\bdoes\s+not\s+(?:characterize|establish|contain|show)\b", lowered
        ):
            continue
        if not re.search(r"\b(?:our\s+)?(?:training\s+)?dataset\b", lowered):
            continue
        challenge_markers = sum(
            bool(re.search(pattern, lowered))
            for pattern in (
                r"\bnoisy\s+(?:nature|text|messages?|posts?)\b",
                r"\bmisspell\w*\b",
                r"\bslang\b",
                r"\b(?:unusual|special)\s+character\w*\b",
                r"\b(?:out-of-vocabulary|oov)\b",
                r"\babbreviations?\b",
            )
        )
        if challenge_markers < 2:
            continue
        output.append(
            StructuredBooleanResolution(
                polarity="yes",
                quote=window,
                quantifier="some",
                reason="explicit_current_dataset_challenges",
            )
        )
    return tuple(output)


def _supervision_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    asks_fully_supervised = "fully supervised" in lowered_question
    asks_unsupervised = bool(
        "unsupervised" in lowered_question
        and re.search(r"\b(?:approach|method|system)\b", lowered_question)
    )
    if not (asks_fully_supervised or asks_unsupervised):
        return ()
    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=4):
        lowered = window.lower()
        if asks_fully_supervised:
            if re.search(r"\b(?:semi-supervised|unsupervised|unlabeled)\b", lowered):
                continue
            complete_labels = re.search(
                r"\b(?:each|every|all)\b[^.!?]{0,80}\b(?:label(?:ed|led)|labels?)\b",
                lowered,
            )
            trained_predictor = re.search(
                r"\b(?:feed|train)\w*\b.{0,220}"
                r"\b(?:classifier|network|model)\b.{0,500}"
                r"\b(?:class|classif|predict)\w*\b",
                lowered,
            )
            if complete_labels and trained_predictor:
                output.append(
                    StructuredBooleanResolution(
                        polarity="yes",
                        quote=window,
                        quantifier="all",
                        reason="explicit_fully_labeled_training_pipeline",
                    )
                )
        if asks_unsupervised:
            named_supervised_classifier = re.search(
                r"\b(?:supervised\s+classifiers?|support\s+vector\s+machines?|"
                r"svm|adaboost|random\s+forests?)\b",
                lowered,
            )
            trained_classifier = re.search(
                r"\bclassifiers?\b[^.!?]{0,100}\btrain(?:ed|ing)?\b|"
                r"\btrain(?:ed|ing)?\b[^.!?]{0,100}\bclassifiers?\b",
                lowered,
            )
            supervised_protocol = re.search(
                r"\b(?:labeled|cross[- ]validation|spammers?\s+and\s+"
                r"legitimate[- ]users?)\b",
                lowered,
            )
            if (
                named_supervised_classifier
                and trained_classifier
                and supervised_protocol
            ):
                output.append(
                    StructuredBooleanResolution(
                        polarity="no",
                        quote=window,
                        quantifier="none",
                        reason="explicit_supervised_detection_pipeline",
                    )
                )
    return tuple(output)


def _custom_nlu_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        re.search(r"\boff[- ]the[- ]shelf\b", lowered_question)
        and re.search(r"\bnlp\s+systems?\b", lowered_question)
        and re.search(r"\bassi(?:st|t)\w*\b", lowered_question)
    ):
        return ()
    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=2):
        lowered = window.lower()
        if re.search(r"\boff[- ]the[- ]shelf\b", lowered):
            continue
        custom_unit = re.search(
            r"\b(?:we|the\s+authors?)\s+implement(?:ed|ing)?\b[^.!?]{0,100}"
            r"\b(?:nlu|natural\s+language\s+understanding)\b[^.!?]{0,120}"
            r"\b(?:handcrafted\s+rules?|regular\s+expressions?|regex)\b",
            lowered,
        )
        if custom_unit:
            output.append(
                StructuredBooleanResolution(
                    polarity="no",
                    quote=window,
                    quantifier="none",
                    reason="explicit_custom_nlu_implementation",
                )
            )
    return tuple(output)


def _qualitative_comparison_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        re.search(r"\b(?:show|provide|illustrate)\w*\b", lowered_question)
        and re.search(r"\bexamples?\b", lowered_question)
        and "conflict" in lowered_question
        and "attention" in lowered_question
        and re.search(r"\b(?:better|outperform|improv)\w*\b", lowered_question)
    ):
        return ()
    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=3):
        lowered = window.lower()
        if re.search(r"\bdo\s+not\s+(?:show|provide|include)\b", lowered):
            continue
        examples = re.search(
            r"\b(?:show|provide|illustrate)\w*\b[^.!?]{0,100}"
            r"\b(?:qualitative\s+results?|examples?|cases?)\b",
            lowered,
        )
        comparison = re.search(
            r"\b(?:attention\s*(?:and|\+|with)\s*conflict|"
            r"conflict\s*(?:and|\+|with)\s*attention|conflict\s+model)\b"
            r"[^.!?]{0,160}\b(?:better|succeed|correct|outperform)\w*\b|"
            r"\b(?:better|succeed|correct|outperform)\w*\b[^.!?]{0,160}"
            r"\b(?:attention|conflict)\b",
            lowered,
        )
        if examples and comparison:
            output.append(
                StructuredBooleanResolution(
                    polarity="yes",
                    quote=window,
                    quantifier="some",
                    reason="explicit_qualitative_comparison_examples",
                )
            )
    return tuple(output)


def _derogatory_label_analysis_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        re.search(r"\b(?:analy[sz]e|inspect|study|compare)\w*\b", lowered_question)
        and re.search(r"\bspecific\b", lowered_question)
        and re.search(
            r"\b(?:derogatory|offensive)\s+(?:words?|terms?|labels?)\b",
            lowered_question,
        )
    ):
        return ()
    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=3):
        lowered = window.lower()
        if re.search(r"\bdoes\s+not\s+(?:analy[sz]e|inspect|study|compare)\b", lowered):
            continue
        current_focus = re.search(
            r"\b(?:primary|main)\s+focus\s+of\s+this\s+study\b"
            r"[^.!?]{0,160}\b(?:compar|analy[sz]|study)\w*\b"
            r"[^.!?]{0,120}\b(?:labels?|words?|terms?)\b",
            lowered,
        )
        derogatory_label = re.search(
            r"\b(?:derogatory|offensive|outdated)\b",
            lowered,
        )
        if current_focus and derogatory_label:
            output.append(
                StructuredBooleanResolution(
                    polarity="yes",
                    quote=window,
                    quantifier="some",
                    reason="explicit_current_derogatory_label_analysis",
                )
            )
    return tuple(output)
