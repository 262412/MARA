from __future__ import annotations

import re

from .qasper_boolean import stemmed_content_tokens


def candidate_answer_clauses(candidate: str, *, question: str) -> list[str]:
    text = str(candidate or "")
    latex_phrases = [
        " ".join(match.split())
        for match in re.findall(r"\\text\{([^{}]+)\}", text)
        if " ".join(match.split())
    ]
    question_tokens = stemmed_content_tokens(question)
    answer_phrases = [
        phrase
        for phrase in latex_phrases
        if stemmed_content_tokens(phrase) - question_tokens
    ]
    if answer_phrases:
        return list(dict.fromkeys(answer_phrases))
    clauses: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        sentence = re.sub(
            r"^.*?\b(?:include(?:s|d|ing)?|consists?\s+of|comprises?)\s+",
            "",
            sentence,
            count=1,
            flags=re.IGNORECASE,
        )
        clauses.extend(
            clause.strip(" ,.;:")
            for clause in re.split(
                r"\s*[,;]\s*|\s+(?:and|but|while|whereas)\s+|\s*\+\s*",
                sentence,
                flags=re.IGNORECASE,
            )
            if clause.strip(" ,.;:")
        )
    return list(dict.fromkeys(clauses))


def candidate_subject_phrase(clause: str) -> str:
    match = re.match(
        r"^(?P<subject>[^,;:.!?]{1,120}?)\s+"
        r"(?:is|are|refers?\s+to|means|denotes?)\b",
        str(clause or "").strip(),
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""
    subject = match.group("subject").strip()
    return subject if len(re.findall(r"[A-Za-z0-9]+", subject)) <= 8 else ""
