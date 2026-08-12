from __future__ import annotations

import re


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
