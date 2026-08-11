from __future__ import annotations

import re


def _relation_surface_tokens(relation: str) -> set[str]:
    surfaces = {
        "annotate": {
            "annotate",
            "construct",
            "crowdsource",
            "crowdsourced",
            "label",
        },
        "compare": {"compare", "contrast", "outperform"},
        "create": {
            "build",
            "built",
            "collect",
            "compile",
            "construct",
            "create",
            "develop",
            "gather",
            "generate",
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
        "improve": {
            "benefit",
            "enhance",
            "improve",
            "improvement",
            "improvements",
            "increase",
        },
        "provide": {
            "available",
            "distribute",
            "provide",
            "publish",
            "release",
            "share",
        },
        "train": {
            "finetune",
            "fine-tune",
            "optimize",
            "pretrain",
            "pretrained",
            "train",
        },
        "use": {
            "apply",
            "employ",
            "incorporate",
            "introduce",
            "leverage",
            "rely",
            "use",
            "used",
            "utilize",
        },
        "validate": {"check", "control", "validate", "verify"},
    }
    return surfaces.get(relation, {relation})


def _object_token(token: str) -> str:
    aliases = {
        "components": "component",
        "own": "",
        "our": "",
        "their": "",
        "this": "",
        "these": "",
        "those": "",
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
        "our",
        "own",
        "their",
        "this",
        "these",
        "those",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) > 2 and token not in stopwords
    }
