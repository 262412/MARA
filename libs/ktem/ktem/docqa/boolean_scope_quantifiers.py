from __future__ import annotations

import re

from .boolean_annotation_count import (
    annotation_count_question,
    annotation_count_scope_complete,
    annotation_count_target,
)
from .boolean_proposition_tokens import _object_token
from .boolean_relations import (
    boolean_relation_lemmas,
    boolean_relations_align,
    primary_boolean_relation,
)
from .boolean_scope_alternatives import (
    _other_than_scope_complete,
    other_quantified_object_noun,
    other_quantified_scope_complete,
    other_quantifier_present,
)
from .boolean_scope_language import _current_language_data_context  # noqa: F401
from .boolean_scope_language import _english_closed_scope  # noqa: F401
from .boolean_scope_language import _language_data_question  # noqa: F401
from .boolean_scope_language import _non_english_counterexample  # noqa: F401
from .boolean_scope_language import _scope_excerpt  # noqa: F401
from .boolean_scope_quantifier_values import _number_value


def _has_closed_quantifier(question: str) -> bool:
    return _closed_quantifier(question) != "none"


def _closed_quantifier(question: str) -> str:
    value = str(question or "")
    lowered = value.lower()
    if annotation_count_question(value):
        return f"count:{annotation_count_target(value)}"
    if re.search(r"\b(?:only|exclusively|solely)\b", lowered):
        return "only"
    if re.search(r"\b(?:all|every|each)\b", lowered):
        return "all"
    if re.search(r"\bboth\b", lowered):
        return "both"
    if re.search(r"\b(?:some|any)\b", lowered):
        return "some" if re.search(r"\bsome\b", lowered) else "any"
    if other_quantifier_present(value):
        return "other"
    count_match = re.search(
        r"\b(?:the\s+)?(two|three|four|five|six|seven|eight|nine|[2-9])\s+"
        r"[a-z][a-z-]*s\b",
        lowered,
    )
    return f"count:{_number_value(count_match.group(1))}" if count_match else "none"


def _quantified_object_scope_complete(
    question: str,
    quote: str,
    *,
    quantifier: str,
    verdict: str = "",
) -> bool:
    relation_spans = _target_relation_spans(question, quote)
    if not relation_spans:
        return False
    if quantifier == "only":
        return _only_quantified_scope_complete(question, quote, relation_spans)
    if quantifier == "all":
        return _all_quantified_scope_complete(question, quote, relation_spans)
    if quantifier == "both":
        return _both_quantified_scope_complete(question, quote, relation_spans)
    if quantifier in {"some", "any"}:
        return _existential_quantified_scope_complete(
            question,
            quote,
            relation_spans,
            quantifier,
            verdict,
        )
    if quantifier == "other":
        return other_quantified_scope_complete(
            _quantified_object_noun(question, "other"),
            quote,
            relation_spans,
            question=question,
            verdict=verdict,
        )
    if quantifier.startswith("count:"):
        return _counted_quantified_scope_complete(
            question,
            quote,
            relation_spans,
            quantifier,
        )
    return True


def _existential_quantified_scope_complete(
    question: str,
    quote: str,
    relation_spans: list[str],
    quantifier: str,
    verdict: str,
) -> bool:
    """Require one explicit object for ``some``/``any`` propositions.

    ``some`` is existential: one exact object mention is sufficient.  ``any``
    is retained as a distinct typed quantifier for authority traces, but it
    still cannot be satisfied by a relation-only sentence or by a question
    token copied into an evidence quote.
    """

    noun = _quantified_object_noun(question, quantifier)
    lowered_question = str(question or "").lower()
    if (
        "task" in lowered_question
        and (
            re.search(r"\b(?:these|those|aforementioned)\s+tasks?\b", lowered_question)
            or re.search(r"\btasks?\s+mentioned\b", lowered_question)
        )
        and relation_spans
    ):
        # Deictic task sets are established by the surrounding experiment
        # frame; the source need not repeat a synthetic noun such as
        # ``tasks mentioned`` in every predicate clause.
        return True
    if not noun:
        return False
    if quantifier == "any" and re.search(r"\bother\s+than\b", lowered_question):
        return _other_than_scope_complete(
            question,
            noun,
            relation_spans,
            verdict=verdict,
        )
    for span in relation_spans:
        if not _span_mentions_object_noun(span, noun):
            continue
        if quantifier == "any" and _quantified_object_exception(
            quote,
            noun=noun,
        ):
            # ``any ... other than X`` is a complete negative/exclusion
            # proposition when the exact relation span names the object.
            return True
        if _quantified_object_exception(quote, noun=noun):
            continue
        return True
    return False


def _only_quantified_scope_complete(
    question: str,
    quote: str,
    relation_spans: list[str],
) -> bool:
    noun = _quantified_object_noun(question, "only")
    complete = any(
        (
            _quantifier_binds_object_noun(
                span,
                noun,
                markers=("only", "exclusively", "solely"),
            )
            if noun
            else re.search(
                r"\b(?:only|exclusively|solely)\b",
                span,
                re.IGNORECASE,
            )
        )
        for span in relation_spans
    )
    return complete and not _only_scope_has_extra_object(question, quote, noun)


def _all_quantified_scope_complete(
    question: str,
    quote: str,
    relation_spans: list[str],
) -> bool:
    named_objects = _named_quantified_objects(question, "all")
    if named_objects:
        complete = _named_objects_in_relation_spans(named_objects, relation_spans)
        return complete and not _quantified_object_exception(
            quote,
            named_objects=named_objects,
        )
    noun = _quantified_object_noun(question, "all")
    complete = any(
        _quantifier_binds_object_noun(
            span,
            noun,
            markers=("all", "every", "each"),
        )
        for span in relation_spans
    )
    return complete and not _quantified_object_exception(quote, noun=noun)


def _both_quantified_scope_complete(
    question: str,
    quote: str,
    relation_spans: list[str],
) -> bool:
    named_objects = _named_quantified_objects(question, "both")
    if named_objects:
        complete = _named_objects_in_relation_spans(named_objects, relation_spans)
        return complete and not _quantified_object_exception(
            quote,
            named_objects=named_objects,
        )
    noun = _quantified_object_noun(question, "both")
    complete = any(
        _counted_object_scope_complete(span, noun, required=2)
        or _binary_comparison_scope_complete(question, span)
        for span in relation_spans
    )
    return complete and not _quantified_object_exception(quote, noun=noun)


def _binary_comparison_scope_complete(question: str, span: str) -> bool:
    if primary_boolean_relation(question) != "compare":
        return False
    transitive = re.search(
        r"\b(?:outperform(?:s|ed|ing)?|beat(?:s|en|ing)?|surpass(?:es|ed|ing)?|"
        r"exceed(?:s|ed|ing)?)\b",
        span,
        flags=re.IGNORECASE,
    )
    if transitive is not None:
        return _comparison_argument(
            span[: transitive.start()]
        ) and _comparison_argument(span[transitive.end() :])
    explicit = re.search(
        r"\b(?:compar(?:e|es|ed|ing)|contrast(?:s|ed|ing)?)\b"
        r"(?P<left>.+?)\b(?:and|with|to|against|versus|vs\.?)\b(?P<right>.+)",
        span,
        flags=re.IGNORECASE,
    )
    return bool(
        explicit
        and _comparison_argument(explicit.group("left"))
        and _comparison_argument(explicit.group("right"))
    )


def _comparison_argument(value: str) -> bool:
    ignored = {
        "a",
        "an",
        "authors",
        "our",
        "paper",
        "study",
        "the",
        "their",
        "this",
        "we",
    }
    return any(
        token not in ignored
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
    )


def _counted_quantified_scope_complete(
    question: str,
    quote: str,
    relation_spans: list[str],
    quantifier: str,
) -> bool:
    required = int(quantifier.partition(":")[2])
    if annotation_count_scope_complete(question, quote, required_count=required):
        return True
    noun = _quantified_object_noun(question, quantifier)
    complete = any(
        _counted_object_scope_complete(span, noun, required=required)
        for span in relation_spans
    )
    return complete and not _quantified_object_exception(quote, noun=noun)


def _named_objects_in_relation_spans(
    named_objects: tuple[str, str],
    relation_spans: list[str],
) -> bool:
    return any(
        all(
            _normalized_object_phrase(value) in _normalized_object_phrase(span)
            for value in named_objects
        )
        for span in relation_spans
    )


def _target_relation_spans(question: str, quote: str) -> list[str]:
    target = primary_boolean_relation(question)
    if not target:
        return []
    output: list[str] = []
    statements = re.split(r"(?:\r?\n)+|(?<=[.!?;])\s+", str(quote or ""))
    for statement in statements:
        clauses = re.split(
            r"\s+(?:but|however|yet|whereas)\s+",
            statement,
            flags=re.IGNORECASE,
        )
        for clause in clauses:
            parts = re.split(r"\s+and\s+", clause, flags=re.IGNORECASE)
            relational = [part for part in parts if boolean_relation_lemmas(part)]
            candidates = parts if len(relational) > 1 else [clause]
            output.extend(
                part.strip()
                for part in candidates
                if target in boolean_relation_lemmas(part)
                or boolean_relations_align(question, part)
            )
    return output


def _quantified_object_noun(question: str, quantifier: str) -> str:
    if quantifier.startswith("count:"):
        prefix = r"(?:the\s+)?(?:two|three|four|five|six|seven|eight|nine|[2-9])"
    elif quantifier == "all":
        prefix = r"(?:all|every|each)"
    else:
        prefix = re.escape(quantifier)
    if quantifier == "other" and (noun := other_quantified_object_noun(question)):
        return noun
    if quantifier in {"any", "some"}:
        alternative = re.search(
            rf"\b{re.escape(quantifier)}\s+other\s+([a-z][a-z-]*s?)\b",
            str(question or ""),
            flags=re.IGNORECASE,
        )
        if alternative is not None:
            return _singular_object_noun(alternative.group(1))
        excluded = re.search(
            rf"\b{re.escape(quantifier)}\s+([a-z][a-z-]*s?)\s+other\s+than\b",
            str(question or ""),
            flags=re.IGNORECASE,
        )
        if excluded is not None:
            return _singular_object_noun(excluded.group(1))
    match = re.search(
        rf"\b{prefix}\s+(?:[a-z0-9][a-z0-9-]*\s+){{0,2}}" r"([a-z][a-z-]*s?)\b",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    return _singular_object_noun(match.group(1)) if match else ""


def _counted_object_scope_complete(span: str, noun: str, *, required: int) -> bool:
    if not noun or not _span_mentions_object_noun(span, noun):
        return False
    number_words = {
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
    }
    explicit_count = re.search(
        rf"\b(?:{required}|{number_words[required]}|both)\b"
        rf"(?:\s+[a-z][a-z0-9_-]*){{0,3}}\s+{re.escape(noun)}s?\b",
        span,
        flags=re.IGNORECASE,
    )
    if explicit_count:
        return True
    noun_mentions = re.findall(rf"\b{re.escape(noun)}s?\b", span, re.IGNORECASE)
    if len(noun_mentions) >= required:
        return True
    return _coordinated_object_count(span, noun=noun) >= required


def _span_mentions_object_noun(span: str, noun: str) -> bool:
    return bool(noun) and bool(
        re.search(rf"\b{re.escape(noun)}s?\b", span, flags=re.IGNORECASE)
    )


def _quantifier_binds_object_noun(
    span: str,
    noun: str,
    *,
    markers: tuple[str, ...],
) -> bool:
    if not noun:
        return False
    marker_pattern = "|".join(re.escape(marker) for marker in markers)
    modifier = r"(?:\s+(?!(?:and|or)\b)[a-z0-9][a-z0-9_-]*)"
    return bool(
        re.search(
            rf"\b(?:{marker_pattern})\b{modifier}{{0,2}}\s+" rf"{re.escape(noun)}s?\b",
            span,
            flags=re.IGNORECASE,
        )
    )


def _quantified_object_exception(
    quote: str,
    *,
    noun: str = "",
    named_objects: tuple[str, str] | None = None,
) -> bool:
    full_quote = str(quote or "")
    clauses = re.split(
        r"(?:\r?\n)+|[.;]|\s+(?:but|however|yet|whereas)\s+",
        full_quote,
        flags=re.IGNORECASE,
    )
    negative = re.compile(
        r"\b(?:did\s+not|does\s+not|do\s+not|not|never|no|omit(?:ted|s)?|"
        r"exclud(?:e|ed|es)|except|fail(?:ed|s)?\s+to|without)\b",
        flags=re.IGNORECASE,
    )
    for clause in clauses:
        normalized = _normalized_object_phrase(clause)
        relevant = (
            _span_mentions_object_noun(clause, noun)
            if noun
            else any(
                _normalized_object_phrase(value) in normalized
                for value in named_objects or ()
            )
        )
        if (
            not relevant
            and noun
            and _span_mentions_object_noun(full_quote, noun)
            and re.search(
                r"\b(?:one|some|several|few|two|three|four|five|six|seven|"
                r"eight|nine|[1-9])\b",
                clause,
                flags=re.IGNORECASE,
            )
        ):
            relevant = True
        if relevant and negative.search(clause):
            return True
    return False


def _only_scope_has_extra_object(question: str, quote: str, noun: str) -> bool:
    value = str(quote or "")
    if noun and re.search(
        rf"\b{re.escape(noun)}s?\b\s*,?\s*"
        r"(?:except|plus|together\s+with|along\s+with|with\s+\w+(?:\s+\w+)*\s+"
        r"as\s+well)\b",
        value,
        flags=re.IGNORECASE,
    ):
        return True
    if noun and _coordinated_non_target_object(value, noun):
        return True
    target = primary_boolean_relation(question)
    clauses = re.split(
        r"[.;]|\s+(?:but|however|yet|whereas|and)\s+",
        str(quote or ""),
        flags=re.IGNORECASE,
    )
    target_seen = False
    for clause in clauses:
        has_target = target in boolean_relation_lemmas(clause)
        inherited_target = target_seen and bool(
            re.search(r"\b(?:also|additionally|as\s+well)\b", clause, re.IGNORECASE)
        )
        if has_target:
            target_seen = True
        if not (has_target or inherited_target):
            continue
        if noun and _span_mentions_object_noun(clause, noun):
            continue
        object_tokens = {
            token
            for token in re.findall(r"[a-z][a-z0-9_-]+", clause.lower())
            if token
            not in {
                "also",
                "and",
                "evaluated",
                "evaluate",
                "only",
                "the",
                "they",
                "we",
            }
        }
        if object_tokens:
            return True
    return False


def _coordinated_non_target_object(quote: str, noun: str) -> bool:
    connector = re.compile(
        rf"\b{re.escape(noun)}s?\b\s*(?:,\s*)?"
        r"(?:and|or|plus|as\s+well\s+as|along\s+with|together\s+with|with)\s+"
        r"(?P<object>(?:(?:a|an|the|one|two|three|four|five|six|seven|eight|"
        r"nine|some|several)\s+)?[a-z][a-z0-9_-]*)\b",
        flags=re.IGNORECASE,
    )
    for match in connector.finditer(str(quote or "")):
        candidate = re.sub(
            r"^(?:a|an|the|one|two|three|four|five|six|seven|eight|nine|"
            r"some|several)\s+",
            "",
            match.group("object"),
            flags=re.IGNORECASE,
        )
        if _singular_object_noun(candidate) != noun:
            return True
    return False


def _singular_object_noun(value: str) -> str:
    lowered = str(value or "").lower()
    return lowered[:-1] if lowered.endswith("s") else lowered


def _named_quantified_objects(
    question: str,
    marker: str,
) -> tuple[str, str] | None:
    match = re.search(
        rf"\b{re.escape(marker)}\s+(.+?)\s+and\s+(.+?)(?:\?|$)",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    left = _trim_object_phrase(match.group(1))
    right = _trim_object_phrase(match.group(2))
    return (left, right) if left and right else None


def _trim_object_phrase(value: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_-]+", str(value or ""))
    while tokens and tokens[0].lower() in {"the", "a", "an"}:
        tokens.pop(0)
    for index, token in enumerate(tokens):
        if boolean_relation_lemmas(token):
            tokens = tokens[:index]
            break
    while tokens and tokens[-1].lower() in {
        "are",
        "did",
        "does",
        "is",
        "was",
        "were",
    }:
        tokens.pop()
    return " ".join(tokens)


def _coordinated_object_count(value: str, *, noun: str) -> int:
    """Count explicitly coordinated entities immediately bound to the noun.

    Capitalized words elsewhere in a passage are not object evidence: papers
    routinely mention languages, locations, topic labels, and abbreviations in
    the same sentence as a single dataset.  A count is therefore accepted only
    when two proper-name entities are coordinated directly before ``noun``.
    """

    if not noun:
        return 0
    entity = r"[A-Z][A-Za-z0-9_-]*[A-Za-z0-9]"
    coordinated = re.compile(
        rf"\b(?P<objects>{entity}(?:\s*,?\s*(?:and|or)\s*{entity})+)\s+"
        rf"{re.escape(noun)}s?\b",
    )
    for match in coordinated.finditer(str(value or "")):
        names = re.findall(rf"\b{entity}\b", match.group("objects"))
        if len(names) >= 2 and all(_looks_like_named_dataset(name) for name in names):
            return len(names)
    return 0


def _looks_like_named_dataset(value: str) -> bool:
    token = str(value or "")
    # The object-coordination matcher already requires two names to appear
    # directly before the dataset noun.  Acronym-style dataset names such as
    # ``MNLI`` and ``SNLI`` therefore remain safe even when they are all caps;
    # isolated abbreviations elsewhere in a passage never reach this helper.
    return bool(re.search(r"[A-Z].*[A-Z]", token))


def _normalized_object_phrase(value: str) -> str:
    return " ".join(
        token
        for raw in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if (token := _object_token(raw))
    )
