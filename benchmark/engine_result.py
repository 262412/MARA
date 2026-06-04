from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EngineRunResult:
    answer: str
    predicted_pages: list[int | str] = field(default_factory=list)
    predicted_sources: list[str] = field(default_factory=list)
    predicted_element_ids: list[str] = field(default_factory=list)
    retrieved_hits: list[dict[str, Any]] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    cache: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, Any] = field(default_factory=dict)
    context_preview: str = ""
    retrieval_trace: list[dict[str, Any]] = field(default_factory=list)
    agent_trace: list[dict[str, Any]] = field(default_factory=list)
    evidence_metadata: dict[str, Any] = field(default_factory=dict)
    controller_trace: list[dict[str, Any]] = field(default_factory=list)
    controller_decision: dict[str, Any] = field(default_factory=dict)
    route_decision: dict[str, Any] = field(default_factory=dict)
    retrieve_decision: dict[str, Any] = field(default_factory=dict)
    verify_decision: dict[str, Any] = field(default_factory=dict)
    guardrail_decision: dict[str, Any] = field(default_factory=dict)
    evidence_bundle: dict[str, Any] = field(default_factory=dict)
    claim_verification: dict[str, Any] = field(default_factory=dict)
    presentation: dict[str, Any] = field(default_factory=dict)
