from __future__ import annotations

import re


def _sentences(text: str) -> tuple[str, ...]:
    return tuple(
        match.group(0).strip()
        for match in re.finditer(
            r"[^!?\n]+?(?:(?<!\d)\.(?!\d)|[!?]+|(?=\n|$))",
            str(text or ""),
        )
        if match.group(0).strip()
    )


def _sentence_windows(
    text: str,
    *,
    maximum_width: int,
) -> tuple[str, ...]:
    sentences = _sentences(text)
    return tuple(
        " ".join(sentences[start : start + width])
        for start in range(len(sentences))
        for width in range(1, maximum_width + 1)
        if start + width <= len(sentences)
    )


def _mentions_non_english_language(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:arabic|chinese|czech|dutch|french|german|greek|hindi|"
            r"italian|japanese|mongolian|persian|portuguese|russian|spanish|"
            r"swedish|turkish)\b",
            str(value or "").lower(),
        )
    )


def _concept_stems(value: str) -> set[str]:
    ignored = {
        "before",
        "input",
        "paper",
        "their",
        "they",
        "this",
    }
    return {
        token[:6]
        for token in re.findall(r"[a-z][a-z0-9-]+", str(value or "").lower())
        if len(token) >= 5 and token not in ignored
    }


def _enumerated_names(value: str) -> tuple[str, ...]:
    normalized = re.sub(r"\s+and\s+", ",", str(value or ""), flags=re.IGNORECASE)
    output = []
    for part in normalized.split(","):
        name = re.sub(r"\([^)]*\)", "", part)
        name = _normalized_name(name)
        if name:
            output.append(name)
    return tuple(output)


def _normalized_name(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _identity_tokens(value: str) -> set[str]:
    generic = {
        "a",
        "an",
        "corpus",
        "data",
        "dataset",
        "in",
        "of",
        "the",
    }
    tokens = set(re.findall(r"[a-z0-9]+", str(value or "").lower())) - generic
    if tokens:
        return tokens
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower())) - {
        "a",
        "an",
        "in",
        "of",
        "the",
    }


def _domain_tokens(value: str) -> set[str]:
    generic = {
        "analysis",
        "balanced",
        "corpus",
        "data",
        "dataset",
        "datasets",
        "for",
        "is",
        "the",
    }
    return {
        token[:-1] if token.endswith("s") and len(token) > 4 else token
        for token in re.findall(r"[a-z][a-z-]+", str(value or "").lower())
        if token not in generic
    }


def _number_value(value: str) -> int | None:
    normalized = str(value or "").strip().lower()
    if normalized.isdigit():
        return int(normalized)
    return {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }.get(normalized)
