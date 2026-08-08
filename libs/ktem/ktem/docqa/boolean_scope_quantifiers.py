from __future__ import annotations

import re

from .boolean_relations import boolean_relation_lemmas, primary_boolean_relation


def _has_closed_quantifier(question: str) -> bool:
    return _closed_quantifier(question) != "none"


def _closed_quantifier(question: str) -> str:
    value = str(question or "")
    lowered = value.lower()
    if re.search(r"\b(?:only|exclusively|solely)\b", lowered):
        return "only"
    if re.search(r"\b(?:all|every|each)\b", lowered):
        return "all"
    if re.search(r"\bboth\b", lowered):
        return "both"
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
    if quantifier.startswith("count:"):
        return _counted_quantified_scope_complete(
            question,
            quote,
            relation_spans,
            quantifier,
        )
    return True


def _only_quantified_scope_complete(
    question: str,
    quote: str,
    relation_spans: list[str],
) -> bool:
    noun = _quantified_object_noun(question, "only")
    complete = any(
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
            )
    return output


def _quantified_object_noun(question: str, quantifier: str) -> str:
    if quantifier.startswith("count:"):
        prefix = r"(?:the\s+)?(?:two|three|four|five|six|seven|eight|nine|[2-9])"
    elif quantifier == "all":
        prefix = r"(?:all|every|each)"
    else:
        prefix = re.escape(quantifier)
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
    return _coordinated_object_count(span) >= required


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


def _coordinated_object_count(value: str) -> int:
    text = str(value or "")
    named = {
        token.casefold()
        for token in re.findall(r"\b[A-Z][A-Za-z0-9_-]*[A-Za-z0-9]\b", text)
        if token.casefold()
        not in {"the", "we", "our", "this", "did", "does", "were", "was"}
    }
    if len(named) >= 2 and re.search(r"\b(?:and|,)\b", text):
        return len(named)
    coordinated = re.search(
        r"\b([a-z][a-z0-9_-]*)\s+(?:and|,)\s+" r"([a-z][a-z0-9_-]*)\s+[a-z][a-z-]*s\b",
        text,
        flags=re.IGNORECASE,
    )
    return 2 if coordinated else 0


def _normalized_object_phrase(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _number_value(value: str) -> int:
    words = {
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
    }
    return words.get(value, int(value) if value.isdigit() else 0)


def _language_data_question(question: str) -> bool:
    lowered = str(question or "").lower()
    return "english" in lowered and bool(
        re.search(r"\b(?:data|dataset|corpus|language|result|experiment)\w*\b", lowered)
    )


def _non_english_counterexample(quote: str) -> bool:
    for statement in re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", str(quote or "")):
        lowered = statement.lower()
        if re.search(
            r"\b(?:non-english|greek|german|french|spanish|chinese|"
            r"japanese|arabic|multilingual)\b",
            lowered,
        ) and re.search(
            r"\b(?:evaluate|evaluated|evaluation|experiment|report|results?|"
            r"test|tested|dataset|corpus)\w*\b",
            lowered,
        ):
            return True
    return False


def _english_closed_scope(quote: str) -> bool:
    lowered = str(quote or "").lower()
    return "english" in lowered and bool(
        re.search(
            r"\b(?:only|exclusively|solely|all (?:the )?(?:data|datasets|corpora)|"
            r"english-speaking countries)\b",
            lowered,
        )
    )


def _current_language_data_context(text: str) -> bool:
    current_actor = re.compile(
        r"\b(?:we|our|current study|this (?:paper|study|work|section))\b",
        flags=re.IGNORECASE,
    )
    data_relation = re.compile(
        r"\b(?:collect|compil|creat|data selection|dataset|corpus|corpora|"
        r"evaluat|experiment|report|results?)\w*\b",
        flags=re.IGNORECASE,
    )
    return any(
        current_actor.search(statement) and data_relation.search(statement)
        for statement in re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", str(text or ""))
    )


def _scope_excerpt(text: str, polarity: str) -> str | None:
    statements = [
        (match.start(), match.end(), match.group(0).strip())
        for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", str(text or ""))
        if match.group(0).strip()
    ]
    windows = list(statements)
    windows.extend(
        (left[0], right[1], text[left[0] : right[1]].strip())
        for left, right in zip(statements, statements[1:])
    )
    candidates = []
    item_has_current_data_context = _current_language_data_context(text)
    for start, end, excerpt in windows:
        if polarity == "no":
            valid = _non_english_counterexample(excerpt)
        else:
            valid = _english_closed_scope(excerpt) and (
                item_has_current_data_context
                or bool(
                    re.search(
                        r"\b(?:report|result|evaluat|experiment|test|dataset|"
                        r"corpus|data)\w*\b",
                        excerpt,
                        flags=re.IGNORECASE,
                    )
                )
            )
        if valid:
            candidates.append((end - start, start, excerpt))
    if not candidates:
        return None
    return min(candidates)[2]
