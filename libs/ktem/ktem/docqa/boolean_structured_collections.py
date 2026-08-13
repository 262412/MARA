from __future__ import annotations

import re

from .boolean_structured_schema import StructuredBooleanResolution
from .boolean_structured_text import (
    _domain_tokens,
    _enumerated_names,
    _identity_tokens,
    _mentions_non_english_language,
    _normalized_name,
    _number_value,
    _sentence_windows,
    _sentences,
)


def _named_membership_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    question_match = re.search(
        r"\b(?:is|was)\s+(?P<member>[A-Za-z][A-Za-z -]*?)\s+"
        r"one\s+of\s+(?:the\s+)?(?P<count>[A-Za-z]+|\d+)\s+"
        r"(?P<noun>languages?)\s+in\s+(?:the\s+)?"
        r"(?P<collection>[^?]+)",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    if question_match is None:
        return ()
    question_count = _number_value(question_match.group("count"))
    if question_count is None:
        return ()
    member = _normalized_name(question_match.group("member"))
    collection_tokens = _identity_tokens(question_match.group("collection"))
    if not member or not collection_tokens:
        return ()

    output: list[StructuredBooleanResolution] = []
    for sentence in _sentences(text):
        match = re.search(
            r"(?P<prefix>[^:]{0,180}\b(?:covers?|includes?|contains?|comprises?))"
            r"\s+(?:the\s+)?(?:following\s+)?"
            r"(?P<count>[A-Za-z]+|\d+)\s+languages?\s*:\s*"
            r"(?P<values>.+?)(?:[.!?]+)?$",
            sentence,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        evidence_count = _number_value(match.group("count"))
        values = _enumerated_names(match.group("values"))
        if (
            evidence_count != question_count
            or len(values) != evidence_count
            or not collection_tokens <= _identity_tokens(match.group("prefix"))
        ):
            continue
        output.append(
            StructuredBooleanResolution(
                polarity="yes" if member in values else "no",
                quote=sentence,
                quantifier=f"count:{evidence_count}",
                reason="explicit_complete_named_enumeration",
            )
        )
    return tuple(output)


def _balanced_distribution_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        "balanced" in lowered_question
        and re.search(r"\b(?:data|datasets?|corpus|corpora)\b", lowered_question)
    ):
        return ()
    question_domain = _domain_tokens(question)
    output: list[StructuredBooleanResolution] = []
    for sentence in _sentences(text):
        lowered = sentence.lower()
        if not re.search(
            r"\b(?:labels?\s+(?:contain|include)|class\s+distribution|"
            r"(?:data|datasets?|corpus)\s+(?:contains?|includes?|comprises?|"
            r"consists?\s+of))\b",
            lowered,
        ):
            continue
        counts = [
            int(match.group("count").replace(",", ""))
            for match in re.finditer(
                r"(?P<count>\d[\d,]*)\s+"
                r"(?P<label>[A-Za-z][A-Za-z-]*)\s+"
                r"(?:sentiments?|examples?|instances?|samples?|items?|labels?|"
                r"tweets?|accounts?)\b",
                sentence,
                flags=re.IGNORECASE,
            )
        ]
        if len(counts) < 2:
            continue
        if question_domain and not question_domain & _domain_tokens(sentence):
            continue
        output.append(
            StructuredBooleanResolution(
                polarity="yes" if len(set(counts)) == 1 else "no",
                quote=sentence,
                quantifier=f"count:{len(counts)}",
                reason="explicit_complete_class_distribution",
            )
        )
    return tuple(output)


def _independent_decoder_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        re.search(r"\bdecoders?\b", lowered_question)
        and re.search(r"\b(?:same|shared?|identical|tied)\b", lowered_question)
        and re.search(r"\b(?:weights?|parameters?)\b", lowered_question)
    ):
        return ()
    output: list[StructuredBooleanResolution] = []
    sentences = _sentences(text)
    for start in range(len(sentences)):
        for width in (1, 2, 3):
            window = " ".join(sentences[start : start + width])
            lowered = window.lower()
            if re.search(
                r"\b(?:same|shared|identical|tied)\s+"
                r"(?:decoder\s+)?(?:weights?|parameters?)\b|"
                r"\b(?:weights?|parameters?)\s+(?:are\s+|were\s+)?"
                r"(?:shared|tied|identical)\b",
                lowered,
            ):
                continue
            independent = re.search(
                r"\b(?:independent|separate|distinct)\s+(?:decoder\s+)?"
                r"(?:lstms?|decoders?)\b",
                lowered,
            )
            component_specific = re.search(
                r"\b(?:one\s+for\s+each|each\s+decoder|"
                r"position-specific|specific\s+language\s+model\s+for\s+each)\b",
                lowered,
            )
            if independent and component_specific:
                output.append(
                    StructuredBooleanResolution(
                        polarity="no",
                        quote=window,
                        quantifier="all",
                        reason="explicit_independent_decoder_parameters",
                    )
                )
                break
    return tuple(output)


def _external_collection_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        re.search(r"\bcollect(?:ed|ing)?\b", lowered_question)
        and re.search(
            r"\b(?:own|our|their)\s+(?:new\s+|original\s+)?"
            r"(?:data|dataset|corpus)\b",
            lowered_question,
        )
    ):
        return ()
    output: list[StructuredBooleanResolution] = []
    for sentence in _sentences(text):
        lowered = sentence.lower()
        if not re.search(
            r"\b(?:we|the\s+authors?)\s+collect(?:ed|ing)?\b[^.!?]{0,100}"
            r"\b(?:data|dataset|corpus)\b",
            lowered,
        ):
            continue
        if re.search(
            r"\b(?:our|their|the\s+authors?'?)\s+own\s+"
            r"(?:data|dataset|corpus)\b|"
            r"\b(?:volunteer|participant|respondent|speaker|annotator|worker)s?\b",
            lowered,
        ):
            continue
        external_source = re.search(
            r"\bfrom\b[^.!?]{0,120}\b(?:existing|public|external|third[- ]party)"
            r"\b[^.!?]{0,40}\b(?:data|dataset|corpus|resource)\b|"
            r"\bfrom\b[^.!?]{0,120}\b(?:talks?|articles?|documents?|texts?)\b"
            r"[^.!?]{0,80}\bextracted\s+from\b[^.!?]{0,80}"
            r"\b(?:corpus|dataset|repository)\b",
            lowered,
        )
        if external_source:
            output.append(
                StructuredBooleanResolution(
                    polarity="no",
                    quote=sentence,
                    quantifier="none",
                    reason="explicit_external_collection_provenance",
                )
            )
    return tuple(output)


def _english_experiment_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        "english" in lowered_question
        and "only" in lowered_question
        and re.search(
            r"\b(?:data|datasets?|corpus|corpora|results?|evaluat|experiments?)\w*\b",
            lowered_question,
        )
    ):
        return ()

    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=3):
        lowered = window.lower()
        if _mentions_non_english_language(lowered):
            continue
        all_tasks = re.search(
            r"\bfor\s+all\s+(?:the\s+)?(?:tasks?|experiments?)\b"
            r"[^.!?]{0,160}\b(?:use|using|evaluate|report)\w*\b"
            r"[^.!?]{0,120}\benglish\b",
            lowered,
        )
        counted_english = re.search(
            r"\b(?:use|using|evaluate|report)\w*\s+"
            r"(?:the\s+)?(?P<count>[a-z]+|\d+)"
            r"(?:\s+[a-z-]+){0,3}\s+english\s+"
            r"(?:data|datasets?|corpora|corpus|messages?|posts?|tweets?)\b",
            lowered,
        )
        counted_inventory = re.search(
            r"\b(?:use|using|evaluate|report)\w*\s+"
            r"(?:the\s+)?(?P<count>[a-z]+|\d+)\s+datasets?\b",
            lowered,
        )
        inventory_complete = False
        inventory_count: int | None = None
        if counted_inventory is not None:
            inventory_count = _number_value(counted_inventory.group("count"))
            inventory_complete = bool(
                inventory_count
                and lowered.count("english") >= inventory_count
                and (
                    ("(a)" in lowered and "(b)" in lowered)
                    or (
                        re.search(r"\b(?:first|one)\b", lowered)
                        and re.search(r"\bsecond\b", lowered)
                    )
                )
            )
        if not (all_tasks or counted_english or inventory_complete):
            continue
        count = (
            _number_value(counted_english.group("count"))
            if counted_english is not None
            else inventory_count
        )
        output.append(
            StructuredBooleanResolution(
                polarity="yes",
                quote=window,
                quantifier=f"count:{count}" if count else "all",
                reason="explicit_closed_english_experiment_scope",
            )
        )
    return tuple(output)


def _shared_lexicon_resolutions(
    question: str,
    text: str,
) -> tuple[StructuredBooleanResolution, ...]:
    lowered_question = str(question or "").lower()
    if not (
        "lexicon" in lowered_question
        and re.search(r"\b(?:same|shared|single|one)\b", lowered_question)
        and re.search(r"\b(?:all|every)\s+languages?\b", lowered_question)
    ):
        return ()
    output: list[StructuredBooleanResolution] = []
    for window in _sentence_windows(text, maximum_width=4):
        lowered = window.lower()
        if re.search(
            r"\b(?:separate|different|distinct|per-language)\s+lexicons?\b|"
            r"\blexicon\s+(?:for|per)\s+each\s+language\b",
            lowered,
        ):
            continue
        single_lexicon = re.search(r"\b(?:the|one|a single)\s+lexicon\b", lowered)
        complete_data = re.search(
            r"\bbuilt\s+(?:over|from)\s+all\s+(?:the\s+)?data\b",
            lowered,
        )
        language_scope = re.search(r"\blanguages?(?:\s+groups?)?\b", lowered)
        if single_lexicon and complete_data and language_scope:
            output.append(
                StructuredBooleanResolution(
                    polarity="yes",
                    quote=window,
                    quantifier="all",
                    reason="explicit_single_lexicon_over_all_language_data",
                )
            )
    return tuple(output)
