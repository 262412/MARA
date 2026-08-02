from __future__ import annotations

import re

_RELATION_GROUPS = {
    "annotate": {"annotate", "construct", "label"},
    "associate": {"associate", "connect", "link", "relate"},
    "compare": {"compare", "contrast", "outperform"},
    "create": {"build", "collect", "compile", "create", "develop"},
    "demonstrate": {"demonstrate", "establish", "prove", "show"},
    "evaluate": {
        "assess",
        "benchmark",
        "conduct",
        "evaluate",
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
        "inspect",
        "investigate",
        "study",
    },
    "learn": {"capture", "learn"},
    "provide": {"available", "provide", "publish", "release"},
    "recommend": {"recommend", "suggest"},
    "require": {"must", "need", "require"},
    "train": {"finetune", "fine-tune", "train"},
    "translate": {"translate"},
    "use": {"apply", "employ", "incorporate", "introduce", "rely", "use"},
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


def boolean_relation_lemmas(value: str) -> set[str]:
    return {
        relation
        for token in re.findall(r"[a-z]+(?:-[a-z]+)?", str(value or "").lower())
        if (relation := boolean_relation_lemma(token))
    }


def primary_boolean_relation(value: str) -> str:
    for token in re.findall(r"[a-z]+(?:-[a-z]+)?", str(value or "").lower()):
        relation = boolean_relation_lemma(token)
        if relation:
            return relation
    return ""


def boolean_relations_align(question: str, evidence: str) -> bool:
    primary = primary_boolean_relation(question)
    if not primary:
        return True
    return primary in boolean_relation_lemmas(evidence)


def boolean_relation_lemma(token: str) -> str:
    normalized = str(token or "").strip().lower()
    normalized = _IRREGULAR_FORMS.get(normalized, normalized)
    direct = _RELATION_BY_FORM.get(normalized)
    if direct:
        return direct
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
