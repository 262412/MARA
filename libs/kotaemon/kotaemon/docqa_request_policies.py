from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class DocQARequestPolicy:
    name: str
    qa_scope_default: str
    page_number_default: int | None
    page_rule: str
    controller_mode_default: str | None
    route_policy_default: str | None
    verification_mode_default: str | None
    verification_domain_rule: str
    origin: str
    allowed_routes_default: tuple[str, ...] | None
    max_context_length_default: int | None
    always_list_fields: tuple[str, ...]
    selected_file_ids_rule: str


WEB_REQUEST_POLICY = DocQARequestPolicy(
    name="web",
    qa_scope_default="page",
    page_number_default=1,
    page_rule="minimum_one",
    controller_mode_default="llm",
    route_policy_default="auto",
    verification_mode_default="light",
    verification_domain_rule="explicit",
    origin="web",
    allowed_routes_default=(),
    max_context_length_default=None,
    always_list_fields=("history", "note_ids", "allowed_routes", "page_image_records"),
    selected_file_ids_rule="none_inherits_empty_clears",
)

MARA_CLI_REQUEST_POLICY = DocQARequestPolicy(
    name="mara_cli",
    qa_scope_default="auto",
    page_number_default=None,
    page_rule="optional",
    controller_mode_default="off",
    route_policy_default="auto",
    verification_mode_default="off",
    verification_domain_rule="explicit",
    origin="cli",
    allowed_routes_default=(),
    max_context_length_default=None,
    always_list_fields=("allowed_routes",),
    selected_file_ids_rule="none_inherits_empty_clears",
)

LEGACY_CLI_REQUEST_POLICY = DocQARequestPolicy(
    name="legacy_cli",
    qa_scope_default="auto",
    page_number_default=None,
    page_rule="optional",
    controller_mode_default=None,
    route_policy_default=None,
    verification_mode_default=None,
    verification_domain_rule="unset",
    origin="cli",
    allowed_routes_default=None,
    max_context_length_default=None,
    always_list_fields=(),
    selected_file_ids_rule="none_inherits_empty_clears",
)

BENCHMARK_REQUEST_POLICY = DocQARequestPolicy(
    name="benchmark",
    qa_scope_default="document",
    page_number_default=None,
    page_rule="first_evidence",
    controller_mode_default=None,
    route_policy_default=None,
    verification_mode_default=None,
    verification_domain_rule="dataset_family_if_unset",
    origin="benchmark",
    allowed_routes_default=None,
    max_context_length_default=16000,
    always_list_fields=("page_image_records", "element_index_records"),
    selected_file_ids_rule="always_list",
)

DOCQA_REQUEST_POLICIES: Mapping[str, DocQARequestPolicy] = MappingProxyType(
    {
        policy.name: policy
        for policy in (
            WEB_REQUEST_POLICY,
            MARA_CLI_REQUEST_POLICY,
            LEGACY_CLI_REQUEST_POLICY,
            BENCHMARK_REQUEST_POLICY,
        )
    }
)


__all__ = [
    "BENCHMARK_REQUEST_POLICY",
    "DOCQA_REQUEST_POLICIES",
    "DocQARequestPolicy",
    "LEGACY_CLI_REQUEST_POLICY",
    "MARA_CLI_REQUEST_POLICY",
    "WEB_REQUEST_POLICY",
]
