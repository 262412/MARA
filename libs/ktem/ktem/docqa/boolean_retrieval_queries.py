from __future__ import annotations

import re

from .boolean_proposition_tokens import _content_tokens
from .boolean_relations import boolean_relation_lemmas
from .boolean_scope_quantifiers import _has_closed_quantifier, _language_data_question


def boolean_retrieval_query(
    question: str,
    *,
    second_round: bool = False,
) -> str:
    text = " ".join(str(question or "").split())
    lowered = text.lower()
    expansions: list[str] = []
    if re.search(r"\bquality\s+control\b", lowered) and re.search(
        r"\bsubject(?:ed)?(?:\s+to)?\b|\bundergo", lowered
    ):
        expansions.append(
            "quality validation synthetic data datasets annotation artifacts "
            "validate quality crowd-sourcing"
        )
    elif _language_data_question(text) and _has_closed_quantifier(text):
        expansions.append(
            "current study experiments results English data "
            "English-speaking countries non-English datasets"
        )
    elif re.search(r"\b(?:experiment|evaluate|test|task)\w*\b", lowered):
        expansions.append(
            "current study authors experiments evaluate tested examples results"
        )
    if second_round:
        expansions.extend(_boolean_second_round_expansion(text))
    if not expansions:
        return text
    return f"{text} {' '.join(expansions)}".strip()


def _boolean_second_round_expansion(question: str) -> tuple[str, ...]:
    relation_aliases = {
        "annotate": (
            "annotate",
            "label",
            "construct",
            "crowdsource",
            "human annotator",
        ),
        "compare": ("compare", "contrast", "outperform"),
        "create": (
            "create",
            "build",
            "collect",
            "construct",
            "gather",
            "compile",
        ),
        "evaluate": ("evaluate", "assess", "test", "benchmark"),
        "inspect": ("inspect", "examine", "analyze", "investigate"),
        "provide": ("provide", "release", "publish", "share", "available"),
        "train": ("train", "fine-tune", "finetune", "optimize"),
        "use": ("use", "apply", "employ", "rely on"),
        "validate": ("validate", "verify", "check", "control"),
    }
    object_aliases = {
        "annotation": ("annotation", "label", "crowdsourcing"),
        "annotations": ("annotation", "label", "crowdsourcing"),
        "code": ("code", "implementation", "source code", "repository"),
        "crowdsource": ("crowdsource", "crowdsourcing", "annotation"),
        "crowdsourcing": (
            "crowdsourcing",
            "crowdsource",
            "human annotator",
            "label",
            "platform",
        ),
        "quality": ("quality", "validity", "reliability"),
        "data": ("data", "dataset", "corpus", "probes"),
        "dataset": ("dataset", "data", "corpus", "probes"),
        "datasets": ("dataset", "data", "corpus", "probes"),
        "model": ("model", "system", "method", "architecture"),
        "models": ("model", "system", "method", "architecture"),
        "platform": ("platform", "service", "tool"),
        "pretrained": ("pretrained", "pre-training", "model"),
        "source": ("source", "repository", "code"),
        "task": ("task", "benchmark", "experiment", "evaluation"),
    }
    expansions: list[str] = []
    for relation in sorted(boolean_relation_lemmas(question)):
        expansions.extend(relation_aliases.get(relation, ()))
    for token in sorted(_content_tokens(question)):
        expansions.extend(object_aliases.get(token, ()))
    lowered = str(question or "").casefold()
    if re.search(r"\bindex(?:ed|ing)(?:-based)?\b", lowered):
        expansions.extend(("indexing-based", "indexing method", "indexed"))
    if re.search(r"\bqa\b|\bquestion answering\b", lowered):
        expansions.extend(("question answering", "answer retrieval"))
    if re.search(r"\bsample\b", lowered):
        expansions.extend(("sample", "silver-standard"))
    if "wikipedia" in lowered:
        expansions.extend(("Wikipedia", "entire Wikipedia"))
    if "semantic role induction" in lowered:
        expansions.extend(("SRI", "semantic roles", "role alignments"))
    if re.search(r"\bparallel\s+(?:data|corpus|corpora)\b", lowered):
        expansions.extend(("parallel corpus", "word alignments", "crosslingual"))
    return tuple(dict.fromkeys(expansions))
