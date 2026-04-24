from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence


class ClaimSupportStatus(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class ClaimEvidenceMatch:
    evidence_text: str
    score: float
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerifiedClaim:
    text: str
    status: ClaimSupportStatus
    score: float
    matches: list[ClaimEvidenceMatch] = field(default_factory=list)

    @property
    def best_match(self) -> ClaimEvidenceMatch | None:
        return self.matches[0] if self.matches else None


@dataclass(frozen=True)
class ClaimVerificationResult:
    answer: str
    claims: list[VerifiedClaim]

    @property
    def has_unsupported_claims(self) -> bool:
        return any(
            claim.status == ClaimSupportStatus.UNSUPPORTED for claim in self.claims
        )

    @property
    def supported_claims(self) -> list[VerifiedClaim]:
        return [
            claim
            for claim in self.claims
            if claim.status == ClaimSupportStatus.SUPPORTED
        ]

    @property
    def unsupported_claims(self) -> list[VerifiedClaim]:
        return [
            claim
            for claim in self.claims
            if claim.status == ClaimSupportStatus.UNSUPPORTED
        ]


@dataclass(frozen=True)
class ClaimRevision:
    text: str
    abstained: bool
    verification_note: str = ""


_BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
_SENTENCE_END_RE = re.compile(r"[.!?\u3002\uff01\uff1f]$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\u3002\uff01\uff1f])\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?%?")
_FORMULA_TERM = r"[A-Za-z0-9]\w*"
_FORMULA_RE = re.compile(
    rf"\b[A-Za-z]\w*\s*=\s*{_FORMULA_TERM}(?:\s*[+\-*/^]\s*{_FORMULA_TERM})*|"
    rf"\b[A-Za-z]\w*\s*[+\-*/^]\s*{_FORMULA_TERM}"
)
_DISCLAIMER_RE = re.compile(
    r"\b("
    r"hello|hi|thanks|thank you|hope this helps|"
    r"not (?:legal|medical|financial) advice|"
    r"cannot provide|i can help|i'm sorry|i am sorry"
    r")\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


def extract_claims(answer: str) -> list[str]:
    """Extract conservative factual claims from common answer formats."""

    claims: list[str] = []
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not _is_candidate_claim_line(line):
            continue
        line = _BULLET_RE.sub("", line).strip()
        claims.extend(_split_claim_sentences(line))
    return claims


def verify_claims(
    answer: str,
    evidence_texts: Sequence[str] | None = None,
    source_documents: Sequence[Any] | None = None,
) -> ClaimVerificationResult:
    evidence_items = _build_evidence_items(evidence_texts or [], source_documents or [])
    verified: list[VerifiedClaim] = []

    for claim_text in extract_claims(answer):
        matches = _rank_matches(claim_text, evidence_items)
        best = matches[0] if matches else None
        status = _support_status(claim_text, best)
        verified.append(
            VerifiedClaim(
                text=claim_text,
                status=status,
                score=best.score if best else 0.0,
                matches=matches[:3],
            )
        )

    return ClaimVerificationResult(answer=answer, claims=verified)


def revise_or_abstain(
    result: ClaimVerificationResult,
    abstain_text: str = "\u6587\u6863\u8bc1\u636e\u65e0\u6cd5\u652f\u6301\u8be5\u56de\u7b54\u3002",
) -> ClaimRevision:
    factual_claims = [
        claim for claim in result.claims if claim.status != ClaimSupportStatus.NEUTRAL
    ]
    supported = [
        claim
        for claim in factual_claims
        if claim.status == ClaimSupportStatus.SUPPORTED
    ]
    unsupported = [
        claim
        for claim in factual_claims
        if claim.status == ClaimSupportStatus.UNSUPPORTED
    ]

    if not factual_claims:
        return ClaimRevision(text=result.answer, abstained=False)

    if unsupported and not supported:
        return ClaimRevision(
            text=abstain_text,
            abstained=True,
            verification_note="All factual claims were unsupported by the evidence.",
        )

    if unsupported:
        note = (
            "Verification note: removed unsupported claim"
            f"{'s' if len(unsupported) != 1 else ''}."
        )
        return ClaimRevision(
            text=_join_claims([claim.text for claim in supported]),
            abstained=False,
            verification_note=note,
        )

    return ClaimRevision(text=result.answer, abstained=False)


def _is_candidate_claim_line(line: str) -> bool:
    if not line:
        return False
    if _HEADING_RE.match(line):
        return False
    if _DISCLAIMER_RE.search(line):
        return False
    content = _BULLET_RE.sub("", line).strip()
    if not content:
        return False
    if len(_tokens(content)) < 3:
        return False
    if not _SENTENCE_END_RE.search(content) and not _has_fact_signal(content):
        return False
    return True


def _split_claim_sentences(text: str) -> list[str]:
    chunks = _SENTENCE_SPLIT_RE.split(text)
    return [
        chunk.strip()
        for chunk in chunks
        if chunk.strip() and not _DISCLAIMER_RE.search(chunk)
    ]


def _build_evidence_items(
    evidence_texts: Sequence[str],
    source_documents: Sequence[Any],
) -> list[tuple[str, dict[str, Any]]]:
    items = [(str(text), {}) for text in evidence_texts if str(text).strip()]
    for doc in source_documents:
        text = getattr(doc, "text", None) or getattr(doc, "content", None) or str(doc)
        metadata = dict(getattr(doc, "metadata", None) or {})
        if str(text).strip():
            items.append((str(text), metadata))
    return items


def _rank_matches(
    claim_text: str,
    evidence_items: Sequence[tuple[str, dict[str, Any]]],
) -> list[ClaimEvidenceMatch]:
    matches = [
        ClaimEvidenceMatch(
            evidence_text=evidence_text,
            score=_support_score(claim_text, evidence_text),
            source_metadata=metadata,
        )
        for evidence_text, metadata in evidence_items
    ]
    return sorted(matches, key=lambda match: match.score, reverse=True)


def _support_status(
    claim_text: str, best_match: ClaimEvidenceMatch | None
) -> ClaimSupportStatus:
    if best_match is None:
        return ClaimSupportStatus.UNSUPPORTED
    if _numbers_conflict(claim_text, best_match.evidence_text):
        return ClaimSupportStatus.UNSUPPORTED
    if _formulae(claim_text) and not _formulae_overlap(
        claim_text, best_match.evidence_text
    ):
        return ClaimSupportStatus.UNSUPPORTED
    return (
        ClaimSupportStatus.SUPPORTED
        if best_match.score >= 0.62
        else ClaimSupportStatus.UNSUPPORTED
    )


def _support_score(claim_text: str, evidence_text: str) -> float:
    claim_norm = _normalize_text(claim_text)
    evidence_norm = _normalize_text(evidence_text)
    if claim_norm and claim_norm in evidence_norm:
        return 1.0

    claim_tokens = _content_tokens(claim_text)
    evidence_tokens = _content_tokens(evidence_text)
    if not claim_tokens:
        return 0.0

    token_overlap = len(claim_tokens & evidence_tokens) / len(claim_tokens)
    number_bonus = (
        0.2
        if _numbers(claim_text) and _numbers_match(claim_text, evidence_text)
        else 0.0
    )
    formula_bonus = (
        0.2
        if _formulae(claim_text) and _formulae_overlap(claim_text, evidence_text)
        else 0.0
    )
    return min(1.0, token_overlap + number_bonus + formula_bonus)


def _normalize_text(text: str) -> str:
    return " ".join(_tokens(text.lower()))


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _content_tokens(text: str) -> set[str]:
    return {token.lower() for token in _tokens(text) if token.lower() not in _STOPWORDS}


def _numbers(text: str) -> set[str]:
    return {
        number.replace(",", "").lower().rstrip("%")
        for number in _NUMBER_RE.findall(text)
    }


def _numbers_match(claim_text: str, evidence_text: str) -> bool:
    claim_numbers = _numbers(claim_text)
    return bool(claim_numbers) and claim_numbers.issubset(_numbers(evidence_text))


def _numbers_conflict(claim_text: str, evidence_text: str) -> bool:
    claim_numbers = _numbers(claim_text)
    evidence_numbers = _numbers(evidence_text)
    return bool(
        claim_numbers
        and evidence_numbers
        and not claim_numbers.issubset(evidence_numbers)
    )


def _formulae(text: str) -> set[str]:
    return {_normalize_formula(match) for match in _FORMULA_RE.findall(text)}


def _formulae_overlap(claim_text: str, evidence_text: str) -> bool:
    claim_formulae = _formulae(claim_text)
    return bool(claim_formulae) and claim_formulae.issubset(_formulae(evidence_text))


def _normalize_formula(formula: str) -> str:
    return re.sub(r"\s+", "", formula.lower())


def _has_fact_signal(text: str) -> bool:
    return bool(_numbers(text) or _formulae(text))


def _join_claims(claims: Iterable[str]) -> str:
    return " ".join(claim.strip() for claim in claims if claim.strip()).strip()


__all__ = [
    "ClaimEvidenceMatch",
    "ClaimRevision",
    "ClaimSupportStatus",
    "ClaimVerificationResult",
    "VerifiedClaim",
    "extract_claims",
    "revise_or_abstain",
    "verify_claims",
]
