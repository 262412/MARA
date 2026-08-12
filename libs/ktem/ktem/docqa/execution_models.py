from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .controller import RetrieveDecision
from .evidence import EvidenceBundle
from .route_selection import ControllerDecision
from .verification import VerifyDecision

RetrieveFn = Callable[[Any, ControllerDecision], dict[str, Any]]
GenerateFn = Callable[[Any, ControllerDecision, EvidenceBundle], str]
RewriteFn = Callable[[Any, ControllerDecision, EvidenceBundle, str], str]


@dataclass(frozen=True)
class GuardrailDecision:
    status: str
    action: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RouteExecutionResult:
    controller_decision: ControllerDecision
    retrieve_decision: RetrieveDecision
    verify_decision: VerifyDecision
    guardrail_decision: GuardrailDecision
    evidence_bundle: EvidenceBundle
    workflow_plan: dict[str, Any] = field(default_factory=dict)
    answer: str = ""
    controller_trace: list[dict[str, Any]] = field(default_factory=list)
    engine_terminal_answer: str = ""
    engine_terminal_state: dict[str, Any] = field(default_factory=dict)
    engine_verify_decision: dict[str, Any] = field(default_factory=dict)
    engine_terminal_guardrail_decision: dict[str, Any] = field(default_factory=dict)
    engine_terminal_evidence_bundle: dict[str, Any] = field(default_factory=dict)
    engine_terminal_projection_hash: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "controller_decision": self.controller_decision.as_dict(),
            "retrieve_decision": self.retrieve_decision.as_dict(),
            "verify_decision": self.verify_decision.as_dict(),
            "guardrail_decision": self.guardrail_decision.as_dict(),
            "evidence_bundle": self.evidence_bundle.as_dict(),
            "workflow_plan": dict(self.workflow_plan),
            "answer": self.answer,
            "controller_trace": list(self.controller_trace),
            "engine_terminal_answer": self.engine_terminal_answer,
            "engine_terminal_state": deepcopy(self.engine_terminal_state),
            "engine_verify_decision": deepcopy(self.engine_verify_decision),
            "engine_terminal_guardrail_decision": deepcopy(
                self.engine_terminal_guardrail_decision
            ),
            "engine_terminal_evidence_bundle": deepcopy(
                self.engine_terminal_evidence_bundle
            ),
            "engine_terminal_projection_hash": self.engine_terminal_projection_hash,
        }
