from __future__ import annotations

import re

_RELATION_GROUPS = {
    "annotate": {
        "annotate",
        "construct",
        "crowdsource",
        "crowdsourced",
        "crowdsourcing",
        "crowd-sourcing",
        "label",
    },
    "associate": {"associate", "connect", "link", "relate"},
    "compare": {"compare", "contrast", "outperform"},
    "contain": {
        "combine",
        "comprise",
        "consume",
        "contain",
        "have",
        "include",
        "involve",
        "merge",
    },
    "create": {
        "add",
        "assemble",
        "build",
        "collect",
        "compile",
        "create",
        "creation",
        "develop",
        "gather",
        "generate",
        "introduce",
    },
    "demonstrate": {"believe", "demonstrate", "establish", "prove", "show"},
    "evaluate": {
        "assess",
        "benchmark",
        "conduct",
        "evaluate",
        "evaluation",
        "experiment",
        "perform",
        "present",
        "report",
        "run",
        "test",
    },
    "inspect": {
        "analyse",
        "analysis",
        "analyze",
        "examine",
        "explore",
        "extract",
        "extraction",
        "inspect",
        "investigate",
        "study",
    },
    "improve": {
        "benefit",
        "effective",
        "effectiveness",
        "enhance",
        "help",
        "helpful",
        "improve",
        "improvement",
        "improvements",
        "increase",
    },
    "learn": {"capture", "learn", "represent"},
    "provide": {"available", "distribute", "provide", "publish", "release", "share"},
    "recommend": {"recommend", "suggest"},
    "require": {"must", "need", "require"},
    "train": {
        "finetune",
        "fine-tune",
        "optimize",
        "pre-training",
        "pretrain",
        "pretrained",
        "train",
    },
    "translate": {"translate"},
    "use": {
        "apply",
        "employ",
        "incorporate",
        "leverage",
        "rely",
        "utilize",
        "use",
    },
    "validate": {"check", "control", "validate", "verify"},
}
_RELATION_BY_FORM = {
    form: canonical for canonical, forms in _RELATION_GROUPS.items() for form in forms
}
_IRREGULAR_FORMS = {
    "built": "build",
    "conducted": "conduct",
    "done": "perform",
    "learnt": "learn",
    "made": "create",
    "ran": "run",
    "shown": "show",
    "taught": "train",
    "used": "use",
    "uses": "use",
}

_QUESTION_RELATION_ALIASES = {
    "add": "create",
    "contain": "contain",
    "explore": "inspect",
    "extract": "inspect",
    "have": "contain",
    "help": "improve",
    "hypothesize": "demonstrate",
    "include": "contain",
    "introduce": "create",
    "involve": "contain",
    "represent": "learn",
}


def boolean_relation_lemmas(value: str) -> set[str]:
    return {
        relation
        for token in re.findall(r"[a-z]+(?:-[a-z]+)?", str(value or "").lower())
        if (relation := boolean_relation_lemma(token))
    }


def primary_boolean_relation(value: str) -> str:
    question_relation = _question_relation(value)
    if question_relation:
        return question_relation
    for token in re.findall(r"[a-z]+(?:-[a-z]+)?", str(value or "").lower()):
        relation = boolean_relation_lemma(token)
        if relation:
            return relation
    return ""


def _question_relation(value: str) -> str:
    text = str(value or "").strip().lower()
    auxiliary = re.match(
        r"^(?:do|does|did|is|are|was|were|has|have|had)\b",
        text,
    )
    if auxiliary is None:
        return ""
    tokens = re.findall(r"[a-z]+(?:-[a-z]+)?", text[auxiliary.end() :])
    if text.startswith(("is ", "are ", "was ", "were ")):
        if re.search(r"\bcompatible\b", text):
            return ""
        relations = [boolean_relation_lemma(token) for token in tokens]
        for preferred in ("improve", "compare", "evaluate"):
            if preferred in relations:
                return preferred
        return next((relation for relation in relations if relation), "attribute")
    if re.match(r"^(?:do|does|did)\s+(?:they|the\s+authors?)\s+model\b", text):
        return "learn"
    for token in tokens:
        relation = boolean_relation_lemma(token) or _QUESTION_RELATION_ALIASES.get(
            token
        )
        if relation:
            return relation
    return ""


def boolean_relations_align(question: str, evidence: str) -> bool:
    primary = primary_boolean_relation(question)
    if not primary:
        return True
    evidence_relations = boolean_relation_lemmas(evidence)
    if primary in evidence_relations:
        return True
    complement = re.search(
        r"\bto\s+([a-z]+(?:-[a-z]+)?)\b",
        str(question or "").lower(),
    )
    if complement is not None:
        complement_relation = boolean_relation_lemma(complement.group(1))
        if complement_relation and complement_relation in evidence_relations:
            return True
    lowered = str(question or "").lower()
    if (
        primary == "use"
        and re.search(r"\b(?:metric|measure|score|evaluation)\w*\b", lowered)
        and "evaluate" in evidence_relations
    ):
        return True
    if (
        primary == "improve"
        and re.search(r"\beffective(?:ness)?\b", lowered)
        and re.search(
            r"\b(?:can(?:not|'t)|can\s+not|could\s+not|not\s+able\s+to|"
            r"unable\s+to)\b"
            r"[^.!?]{0,100}\bwithout\b",
            str(evidence or "").lower(),
        )
    ):
        return True
    if (
        primary == "evaluate"
        and re.search(r"\b(?:experiment|evaluat|test)\w*\b", lowered)
        and re.search(
            r"\bappl(?:y|ies|ied|ying)\b[^.!?]{0,80}\bto\b",
            str(evidence or "").lower(),
        )
    ):
        return True
    return bool(
        primary == "learn"
        and re.search(r"\bfrom\b", lowered)
        and re.search(r"\b(?:text|image|visual|audio)\w*\b", lowered)
        and evidence_relations & {"contain", "use"}
    )


def boolean_relation_lemma(token: str) -> str:
    normalized = str(token or "").strip().lower()
    normalized = _IRREGULAR_FORMS.get(normalized, normalized)
    direct = _RELATION_BY_FORM.get(normalized)
    if direct:
        return direct
    transposed = _adjacent_transposition_relation(normalized)
    if transposed:
        return transposed
    for suffix in ("ing", "ied", "ed", "es", "s"):
        if not normalized.endswith(suffix) or len(normalized) <= len(suffix) + 3:
            continue
        stem = normalized[: -len(suffix)]
        if suffix == "ied":
            stem = f"{stem}y"
        for candidate in (stem, f"{stem}e"):
            relation = _RELATION_BY_FORM.get(candidate)
            if relation:
                return relation
    return ""


def _adjacent_transposition_relation(value: str) -> str:
    """Correct one adjacent transposition in a relation-sized word."""

    if len(value) < 6 or "-" in value:
        return ""
    for index in range(len(value) - 1):
        if value[index] == value[index + 1]:
            continue
        candidate = value[:index] + value[index + 1] + value[index] + value[index + 2 :]
        if relation := _RELATION_BY_FORM.get(candidate):
            return relation
    return ""
