from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from kotaemon.base import AIMessage, HumanMessage, SystemMessage

from .citation_qa_support import MAX_IMAGES
from .format_context import EVIDENCE_MODE_FIGURE
from .utils import find_start_end_phrase

START_ANSWER_PATTERN = "start_phrase:"
END_ANSWER_PATTERN = "end_phrase:"
CITATION_PATTERN = r"citation【(\d+)】"
START_ANSWER = "FINAL ANSWER"
START_CITATION = "CITATION LIST"


@dataclass
class InlineEvidence:
    """List of evidences to support the answer."""

    start_phrase: str | None = None
    end_phrase: str | None = None
    idx: int | None = None


def answer_to_citations(answer: str) -> list[InlineEvidence]:
    citations: list[InlineEvidence] = []
    current_evidence = None

    for line in answer.split("\n"):
        match = re.match(CITATION_PATTERN, line.lower())
        if match:
            try:
                parsed_citation_idx = int(match.group(1))
            except ValueError:
                parsed_citation_idx = None
            if current_evidence:
                citations.append(current_evidence)
                current_evidence = None
            current_evidence = InlineEvidence(idx=parsed_citation_idx)
        else:
            for keyword in [START_ANSWER_PATTERN, END_ANSWER_PATTERN]:
                if line.lower().startswith(keyword):
                    matched_phrase = line[len(keyword) :].strip()
                    if not current_evidence:
                        current_evidence = InlineEvidence(idx=None)
                    if keyword == START_ANSWER_PATTERN:
                        current_evidence.start_phrase = matched_phrase
                    else:
                        current_evidence.end_phrase = matched_phrase
                    break

        if (
            current_evidence
            and current_evidence.end_phrase
            and current_evidence.start_phrase
        ):
            citations.append(current_evidence)
            current_evidence = None

    if current_evidence:
        citations.append(current_evidence)
    return citations


def replace_citation_with_link(answer: str) -> str:
    pattern = r"【\d+】"
    alternate_pattern = r"\[\d+\]"
    multi_pattern = r"【([\d,\s]+)】"

    def split_citations(match):
        numbers = match.group(1).split(",")
        return "".join(f"【{num.strip()}】" for num in numbers)

    answer = re.sub(multi_pattern, split_citations, answer)
    matches = list(re.finditer(pattern, answer))
    if not matches:
        matches = list(re.finditer(alternate_pattern, answer))

    matched_citations = {match.group() for match in matches}
    for citation in matched_citations:
        citation_id = citation[1:-1]
        answer = answer.replace(
            citation,
            (
                "<a href='#' class='citation' "
                f"id='mark-{citation_id}'>【{citation_id}】</a>"
            ),
        )
    return answer.replace(START_CITATION, "")


def build_inline_messages(
    pipeline: Any,
    history: list[tuple[str, str]],
    prompt: str,
    evidence_mode: int,
    images: list[str],
) -> list[HumanMessage | AIMessage | SystemMessage]:
    messages: list[HumanMessage | AIMessage | SystemMessage] = []
    if pipeline.system_prompt:
        messages.append(SystemMessage(content=pipeline.system_prompt))

    for human, ai in history[-pipeline.n_last_interactions :]:
        messages.append(HumanMessage(content=human))
        messages.append(AIMessage(content=ai))

    if pipeline.use_multimodal and evidence_mode == EVIDENCE_MODE_FIGURE:
        messages.append(
            HumanMessage(
                content=[{"type": "text", "text": prompt}]
                + [
                    {"type": "image_url", "image_url": {"url": image}}
                    for image in images[:MAX_IMAGES]
                ],
            )
        )
    else:
        messages.append(HumanMessage(content=prompt))
    return messages


def match_evidence_with_context(answer, docs) -> dict[str, list[dict]]:
    spans: dict[str, list[dict]] = defaultdict(list)
    if not answer.metadata["citation"]:
        return spans

    for evidence_id, evidence in enumerate(answer.metadata["citation"]):
        start_phrase, end_phrase = evidence.start_phrase, evidence.end_phrase
        evidence_idx = evidence.idx
        if evidence_idx is None:
            evidence_idx = evidence_id + 1
        best_match = None
        best_match_length = 0
        best_match_doc_idx = None

        for doc in docs:
            match, match_length = find_start_end_phrase(
                start_phrase, end_phrase, doc.text
            )
            if best_match is None or (
                match is not None and match_length > best_match_length
            ):
                best_match = match
                best_match_length = match_length
                best_match_doc_idx = doc.doc_id

        if best_match is not None and best_match_doc_idx is not None:
            spans[best_match_doc_idx].append(
                {
                    "start": best_match[0],
                    "end": best_match[1],
                    "idx": evidence_idx,
                }
            )
    return spans
