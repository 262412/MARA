from __future__ import annotations

from typing import Any

from .docqa_request_policies import LEGACY_CLI_REQUEST_POLICY


def build_legacy_docqa_request(**request_kwargs: Any):
    from ktem.docqa import DocQARequest

    policy = LEGACY_CLI_REQUEST_POLICY
    request_kwargs.setdefault("qa_scope", policy.qa_scope_default)
    request_kwargs.setdefault("page_number", policy.page_number_default)
    request_kwargs.setdefault("controller_mode", policy.controller_mode_default)
    request_kwargs.setdefault("route_policy", policy.route_policy_default)
    request_kwargs.setdefault("verification_mode", policy.verification_mode_default)
    request_kwargs.setdefault("allowed_routes", policy.allowed_routes_default)
    request_kwargs.setdefault("max_context_length", policy.max_context_length_default)
    request_kwargs.setdefault("origin", policy.origin)
    return DocQARequest(**request_kwargs)
