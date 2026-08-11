from __future__ import annotations

import re


def own_data_provenance_rejection(question: str, quote: str) -> str:
    lowered_question = str(question or "").lower()
    if not re.search(
        r"\b(?:own|our|their)\s+(?:new\s+|original\s+)?data\b|"
        r"\b(?:own|our|their)\s+(?:dataset|corpus)\b",
        lowered_question,
    ):
        return ""
    lowered_quote = str(quote or "").lower()
    if re.search(
        r"\b(?:external|public|borrowed|third[- ]party|provided|existing)\s+"
        r"(?:corpus|dataset|data|resource)\b|"
        r"\bpublicly(?:\s+available)?\s+(?:corpus|dataset|data|resources?)\b|"
        r"\b(?:from|using|based on)\s+(?:an?\s+)?(?:external|public|borrowed|"
        r"third[- ]party|provided|existing)\s+"
        r"(?:corpus|dataset|data|resource)\b",
        lowered_quote,
    ):
        return "external_data_source_does_not_establish_own_collection"
    if re.search(
        r"\b(?:our\s+own|their\s+own|my\s+own|own|original|new|newly\s+"
        r"collected|self[- ]collected|in[- ]house|proprietary)\s+"
        r"(?:data|dataset|corpus)\b|"
        r"\b(?:data|dataset|corpus)\s+(?:ourselves|by\s+(?:us|the\s+authors))\b",
        lowered_quote,
    ):
        return ""
    return "own_data_provenance_not_established"
