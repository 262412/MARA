from __future__ import annotations

import re


def quality_control_evidence_kind(question: str, text: str) -> str:
    lowered_question = str(question or "").lower()
    if not (
        re.search(r"\bquality\s+control\b", lowered_question)
        and re.search(r"\bsubject(?:ed)?(?:\s+to)?\b|\bundergo", lowered_question)
    ):
        return ""
    lowered_text = str(text or "").lower()
    quality_validation = re.search(
        r"\b(?:harder|difficult|impossible)\s+to\s+validate\s+the\s+quality\b"
        r"|\bvalidat\w*\s+(?:the\s+)?quality\b",
        lowered_text,
    ) and re.search(
        r"\b(?:data|dataset|probes?|corpus|corpora)\w*\b",
        lowered_text,
    )
    if quality_validation:
        return "quality_validation"
    if re.search(
        r"\bcontrol(?:led|s)?\s+for\s+(?:annotation\s+)?artifacts?\b"
        r"|\b(?:annotation\s+)?artifacts?\b[^.]{0,60}\bcontrol(?:led|s)?\s+for\b",
        lowered_text,
    ):
        return "annotation_artifact_control"
    return ""
