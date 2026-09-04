from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StructuredBooleanResolution:
    polarity: str
    quote: str
    quantifier: str
    reason: str
