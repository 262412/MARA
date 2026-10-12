"""Public DocQA objects, loaded from their original modules on first access."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import (
        _runtime_doctor,
        _runtime_indexing,
        _runtime_pipeline,
        _runtime_selection,
        _runtime_sessions,
        _runtime_turn,
    )
    from ._runtime_models import (
        DocQADoctorResult,
        DocQAFileRecord,
        DocQAIndexResult,
        DocQARequest,
        DocQAResponse,
        DocQASession,
        DocQASessionSummary,
        DocQATurnUpdate,
    )
    from .artifact_models import (
        ARTIFACT_LABELS,
        ARTIFACT_STATUSES,
        SUPPORTED_ARTIFACT_TYPES,
        normalize_artifact,
    )
    from .controller import (
        ControllerTrace,
        RetrieveDecision,
        RouteDecision,
        VerifyDecision,
        evaluate_retrieval_quality,
        executor_registry,
        parse_planner_decision,
        route_registry,
    )
    from .evidence import EvidenceBundle, EvidenceElement, build_evidence_bundle
    from .execution import (
        ControllerDecision,
        GuardrailDecision,
        RouteExecutionResult,
        execute_controller_turn,
    )
    from .multimodal_index import (
        element_records_from_documents,
        page_image_records_from_documents,
    )
    from .request_policies import (
        BENCHMARK_REQUEST_POLICY,
        DOCQA_REQUEST_POLICIES,
        LEGACY_CLI_REQUEST_POLICY,
        MARA_CLI_REQUEST_POLICY,
        WEB_REQUEST_POLICY,
        DocQARequestPolicy,
    )
    from .runtime import DocQARuntime
    from .workflow import WorkflowPlan, WorkflowStep, build_workflow_plan


_EXPORTS: dict[str, tuple[str, str | None]] = {
    "DocQADoctorResult": ("._runtime_models", "DocQADoctorResult"),
    "DocQAFileRecord": ("._runtime_models", "DocQAFileRecord"),
    "DocQAIndexResult": ("._runtime_models", "DocQAIndexResult"),
    "DocQARequest": ("._runtime_models", "DocQARequest"),
    "DocQAResponse": ("._runtime_models", "DocQAResponse"),
    "DocQARuntime": (".runtime", "DocQARuntime"),
    "DocQASession": ("._runtime_models", "DocQASession"),
    "DocQASessionSummary": ("._runtime_models", "DocQASessionSummary"),
    "DocQATurnUpdate": ("._runtime_models", "DocQATurnUpdate"),
    "DocQARequestPolicy": (".request_policies", "DocQARequestPolicy"),
    "DOCQA_REQUEST_POLICIES": (".request_policies", "DOCQA_REQUEST_POLICIES"),
    "WEB_REQUEST_POLICY": (".request_policies", "WEB_REQUEST_POLICY"),
    "MARA_CLI_REQUEST_POLICY": (".request_policies", "MARA_CLI_REQUEST_POLICY"),
    "LEGACY_CLI_REQUEST_POLICY": (".request_policies", "LEGACY_CLI_REQUEST_POLICY"),
    "BENCHMARK_REQUEST_POLICY": (".request_policies", "BENCHMARK_REQUEST_POLICY"),
    "RouteDecision": (".controller", "RouteDecision"),
    "RetrieveDecision": (".controller", "RetrieveDecision"),
    "EvidenceBundle": (".evidence", "EvidenceBundle"),
    "EvidenceElement": (".evidence", "EvidenceElement"),
    "VerifyDecision": (".controller", "VerifyDecision"),
    "ControllerTrace": (".controller", "ControllerTrace"),
    "ControllerDecision": (".execution", "ControllerDecision"),
    "GuardrailDecision": (".execution", "GuardrailDecision"),
    "RouteExecutionResult": (".execution", "RouteExecutionResult"),
    "WorkflowPlan": (".workflow", "WorkflowPlan"),
    "WorkflowStep": (".workflow", "WorkflowStep"),
    "route_registry": (".controller", "route_registry"),
    "executor_registry": (".controller", "executor_registry"),
    "parse_planner_decision": (".controller", "parse_planner_decision"),
    "evaluate_retrieval_quality": (".controller", "evaluate_retrieval_quality"),
    "build_workflow_plan": (".workflow", "build_workflow_plan"),
    "build_evidence_bundle": (".evidence", "build_evidence_bundle"),
    "execute_controller_turn": (".execution", "execute_controller_turn"),
    "ARTIFACT_LABELS": (".artifact_models", "ARTIFACT_LABELS"),
    "ARTIFACT_STATUSES": (".artifact_models", "ARTIFACT_STATUSES"),
    "SUPPORTED_ARTIFACT_TYPES": (".artifact_models", "SUPPORTED_ARTIFACT_TYPES"),
    "normalize_artifact": (".artifact_models", "normalize_artifact"),
    "page_image_records_from_documents": (
        ".multimodal_index",
        "page_image_records_from_documents",
    ),
    "element_records_from_documents": (
        ".multimodal_index",
        "element_records_from_documents",
    ),
    "_runtime_selection": ("._runtime_selection", None),
    "_runtime_indexing": ("._runtime_indexing", None),
    "_runtime_doctor": ("._runtime_doctor", None),
    "_runtime_pipeline": ("._runtime_pipeline", None),
    "_runtime_sessions": ("._runtime_sessions", None),
    "_runtime_turn": ("._runtime_turn", None),
    # These attributes were already bound by eager imports and have callers.
    "runtime": (".runtime", None),
    "controller": (".controller", None),
    "evidence": (".evidence", None),
    "execution": (".execution", None),
    "artifact_models": (".artifact_models", None),
    "multimodal_index": (".multimodal_index", None),
    "request_policies": (".request_policies", None),
    "workflow": (".workflow", None),
    "_runtime_app": ("._runtime_app", None),
    "_runtime_elements": ("._runtime_elements", None),
    "_runtime_graph": ("._runtime_graph", None),
    "_runtime_mara": ("._runtime_mara", None),
    "_runtime_models": ("._runtime_models", None),
    "_runtime_notebook": ("._runtime_notebook", None),
    "_runtime_utils": ("._runtime_utils", None),
    "boolean_evidence_scope": (".boolean_evidence_scope", None),
    "route_budget": (".route_budget", None),
    "visual_backends": (".visual_backends", None),
    "_runtime_file_service": ("._runtime_file_service", None),
    "_runtime_session_service": ("._runtime_session_service", None),
}

__all__ = [
    "DocQADoctorResult",
    "DocQAFileRecord",
    "DocQAIndexResult",
    "DocQARequest",
    "DocQAResponse",
    "DocQARuntime",
    "DocQASession",
    "DocQASessionSummary",
    "DocQATurnUpdate",
    "DocQARequestPolicy",
    "DOCQA_REQUEST_POLICIES",
    "WEB_REQUEST_POLICY",
    "MARA_CLI_REQUEST_POLICY",
    "LEGACY_CLI_REQUEST_POLICY",
    "BENCHMARK_REQUEST_POLICY",
    "RouteDecision",
    "RetrieveDecision",
    "EvidenceBundle",
    "EvidenceElement",
    "VerifyDecision",
    "ControllerTrace",
    "ControllerDecision",
    "GuardrailDecision",
    "RouteExecutionResult",
    "WorkflowPlan",
    "WorkflowStep",
    "route_registry",
    "executor_registry",
    "parse_planner_decision",
    "evaluate_retrieval_quality",
    "build_workflow_plan",
    "build_evidence_bundle",
    "execute_controller_turn",
    "ARTIFACT_LABELS",
    "ARTIFACT_STATUSES",
    "SUPPORTED_ARTIFACT_TYPES",
    "normalize_artifact",
    "page_image_records_from_documents",
    "element_records_from_documents",
    "_runtime_selection",
    "_runtime_indexing",
    "_runtime_doctor",
    "_runtime_pipeline",
    "_runtime_sessions",
    "_runtime_turn",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    module = import_module(module_name, __name__)
    value = getattr(module, attribute) if attribute is not None else module
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *_EXPORTS})
