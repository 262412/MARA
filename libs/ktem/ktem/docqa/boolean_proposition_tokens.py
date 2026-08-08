from __future__ import annotations

import re


def _relation_surface_tokens(relation: str) -> set[str]:
    surfaces = {
        "annotate": {"annotate", "construct", "label"},
        "compare": {"compare", "contrast", "outperform"},
        "create": {
            "build",
            "built",
            "collect",
            "compile",
            "construct",
            "create",
            "develop",
        },
        "evaluate": {
            "assess",
            "benchmark",
            "conduct",
            "evaluate",
            "experiment",
            "perform",
            "present",
            "report",
            "results",
            "run",
            "test",
        },
        "provide": {"available", "provide", "publish", "release"},
        "train": {"finetune", "fine-tune", "train"},
        "use": {
            "apply",
            "employ",
            "incorporate",
            "introduce",
            "rely",
            "use",
            "used",
        },
    }
    return surfaces.get(relation, {relation})


def _object_token(token: str) -> str:
    aliases = {
        "components": "component",
        "systems": "component",
        "system": "component",
        "packaged": "off_the_shelf",
        "shelf": "off_the_shelf",
        "datasets": "dataset",
        "tasks": "task",
        "authors": "",
        "author": "",
    }
    return aliases.get(token, token.rstrip("s") if token.endswith("s") else token)


def _content_tokens(value: str) -> set[str]:
    stopwords = {
        "are",
        "both",
        "did",
        "does",
        "all",
        "each",
        "every",
        "five",
        "four",
        "nine",
        "never",
        "no",
        "not",
        "only",
        "seven",
        "six",
        "the",
        "three",
        "they",
        "two",
        "was",
        "were",
        "without",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) > 2 and token not in stopwords
    }
