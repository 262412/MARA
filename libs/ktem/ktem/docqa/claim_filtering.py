from __future__ import annotations

import re

_FINAL_ANSWER_MARKER_RE = re.compile(
    r"(?:\*{0,2}\s*)?(?:final\s+answer|answer|最终答案|最终回答)"
    r"(?:[:：]\s*\*{0,2}|\s*\*{1,2}\s*[:：]|\s*[:：])\s*",
    re.IGNORECASE,
)
_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)
_THOUGHT_DETAILS_RE = re.compile(
    r"<details\b[^>]*>\s*<summary\b[^>]*>.*?thought.*?</summary>.*?</details>",
    re.IGNORECASE | re.DOTALL,
)
_UNTAGGED_THOUGHT_PREFIX_RE = re.compile(
    r"^\s*thought\b\s*(?:okay\b|i\b|let\b|let's\b|we\b|the\b|:)",
    re.IGNORECASE,
)
_INITIAL_PERIOD_TOKEN = "__MARA_INITIAL_PERIOD__"
_INITIAL_PERIOD_RE = re.compile(r"\b([A-Z])\.")


def answer_claims(answer: str) -> list[str]:
    cleaned = _clean_text(_remove_markdown_tables(_answer_text(answer)))
    claims = []
    for chunk in _split_sentences(cleaned):
        claim = _clean_claim(chunk)
        if claim and not _is_non_factual_claim(claim):
            claims.append(claim)
    return claims


def clean_answer_text(answer: str) -> str:
    return _clean_display_text(_answer_text(answer))


def _answer_text(answer: str) -> str:
    text = _THINK_BLOCK_RE.sub(" ", str(answer or ""))
    text = _THOUGHT_DETAILS_RE.sub(" ", text)
    markers = list(_FINAL_ANSWER_MARKER_RE.finditer(text))
    if markers:
        text = text[markers[-1].end() :]
    elif _UNTAGGED_THOUGHT_PREFIX_RE.search(text):
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return _remove_inner_abstain_text(text)


def _clean_text(text: str) -> str:
    return " ".join(str(text or "").replace("**", "").split())


def _clean_display_text(text: str) -> str:
    lines = [
        re.sub(r"[ \t]+", " ", line).strip() for line in str(text or "").splitlines()
    ]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _remove_markdown_tables(text: str) -> str:
    return "\n".join(
        line
        for line in str(text or "").splitlines()
        if not _is_markdown_table_line(line)
    )


def _is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return len(cells) > 1


def _split_sentences(text: str) -> list[str]:
    protected = _INITIAL_PERIOD_RE.sub(rf"\1{_INITIAL_PERIOD_TOKEN}", text)
    chunks = re.split(r"(?<=[.!?])\s+", protected)
    return [chunk.replace(_INITIAL_PERIOD_TOKEN, ".") for chunk in chunks]


def _clean_claim(claim: str) -> str:
    text = str(claim or "").replace("**", "")
    text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", text)
    text = re.sub(r"^\s*#+\s*", "", text)
    return " ".join(text.split())


def _remove_inner_abstain_text(answer: str) -> str:
    return str(answer or "").replace("文档证据无法支持该回答。", " ")


def _is_non_factual_claim(claim: str) -> bool:
    lowered = claim.strip().lower()
    if not lowered or lowered in {"---", "—"}:
        return True
    if lowered.startswith(
        (
            "okay,",
            "first,",
            "now,",
            "let's ",
            "i need to ",
            "looking at ",
            "thought ",
            "here's ",
            "here is ",
            "let me ",
            "wait,",
            "hmm,",
            "i think ",
        )
    ):
        return True
    general_explanations = (
        "also known as",
        "calculated as",
        "defined as",
        "different from the current ratio",
        "excludes inventory",
        "measures a company's ability",
    )
    return any(phrase in lowered for phrase in general_explanations) or (
        _is_evidence_commentary_claim(lowered)
    )


def _is_evidence_commentary_claim(lowered: str) -> bool:
    if lowered.startswith(
        (
            "no additional calculation",
            "no additional calculations",
            "no further calculation",
            "no further calculations",
            "no additional interpretation",
            "no additional interpretations",
            "no further interpretation",
            "no further interpretations",
        )
    ):
        return True

    if not re.match(
        r"^this (?:answer|date|figure|information|number|result|value)\b",
        lowered,
    ):
        return False
    commentary_markers = (
        "directly provided",
        "derived from",
        "explicitly stated",
        "provided in the text",
        "provided context",
        "repeated across",
        "confirming",
    )
    return any(marker in lowered for marker in commentary_markers)
