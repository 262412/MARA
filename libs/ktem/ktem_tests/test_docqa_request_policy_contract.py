from __future__ import annotations

import importlib
from dataclasses import FrozenInstanceError, asdict
from types import SimpleNamespace

import pytest
from ktem.docqa import (
    DocQARequest,
    DocQAResponse,
    _runtime_mara,
    _runtime_sessions,
    _runtime_turn,
)
from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
from ktem.pages.chat.chat_docqa_runtime import build_web_docqa_request

EXPECTED_POLICY_MATRIX: dict[str, dict[str, object]] = {
    "web": {
        "qa_scope_default": "page",
        "page_number_default": 1,
        "page_rule": "minimum_one",
        "controller_mode_default": "llm",
        "route_policy_default": "auto",
        "verification_mode_default": "light",
        "verification_domain_rule": "explicit",
        "origin": "web",
        "allowed_routes_default": (),
        "max_context_length_default": None,
        "always_list_fields": (
            "history",
            "note_ids",
            "allowed_routes",
            "page_image_records",
        ),
        "selected_file_ids_rule": "none_inherits_empty_clears",
    },
    "mara_cli": {
        "qa_scope_default": "auto",
        "page_number_default": None,
        "page_rule": "optional",
        "controller_mode_default": "off",
        "route_policy_default": "auto",
        "verification_mode_default": "off",
        "verification_domain_rule": "explicit",
        "origin": "cli",
        "allowed_routes_default": (),
        "max_context_length_default": None,
        "always_list_fields": ("allowed_routes",),
        "selected_file_ids_rule": "none_inherits_empty_clears",
    },
    "legacy_cli": {
        "qa_scope_default": "auto",
        "page_number_default": None,
        "page_rule": "optional",
        "controller_mode_default": None,
        "route_policy_default": None,
        "verification_mode_default": None,
        "verification_domain_rule": "unset",
        "origin": "cli",
        "allowed_routes_default": None,
        "max_context_length_default": None,
        "always_list_fields": (),
        "selected_file_ids_rule": "none_inherits_empty_clears",
    },
    "benchmark": {
        "qa_scope_default": "document",
        "page_number_default": None,
        "page_rule": "unscoped",
        "controller_mode_default": None,
        "route_policy_default": None,
        "verification_mode_default": None,
        "verification_domain_rule": "dataset_family_if_unset",
        "origin": "benchmark",
        "allowed_routes_default": None,
        "max_context_length_default": 16000,
        "always_list_fields": ("page_image_records", "element_index_records"),
        "selected_file_ids_rule": "always_list",
    },
}


RESPONSE_JSON_KEYS = (
    "conversation_id",
    "answer",
    "references_html",
    "references_text",
    "mindmap_html",
    "plot",
    "messages",
    "retrieval_messages",
    "plot_history",
    "state",
    "selected_file_ids",
    "selected_mapping",
    "graph_source_ids",
    "active_file_id",
    "active_file_name",
    "qa_scope",
    "page_number",
    "selected_text",
    "graph_context",
    "reasoning_id",
    "settings",
    "stream_events",
    "graph_cache",
    "agent_trace",
    "evidence_metadata",
    "controller_decision",
    "route_decision",
    "retrieve_decision",
    "verify_decision",
    "guardrail_decision",
    "controller_trace",
    "evidence_bundle",
    "workflow_plan",
    "backend_metadata",
    "artifact",
    "engine_terminal_answer",
    "engine_terminal_state",
    "engine_verify_decision",
    "engine_terminal_guardrail_decision",
    "engine_terminal_evidence_bundle",
    "engine_terminal_projection_hash",
)


def _policies():
    return importlib.import_module("ktem.docqa.request_policies")


def test_named_request_policies_are_immutable_and_match_parity_matrix():
    policies = _policies()
    expected_payloads = {
        name: dict(expected, name=name)
        for name, expected in EXPECTED_POLICY_MATRIX.items()
    }

    assert {
        name: asdict(policy) for name, policy in policies.DOCQA_REQUEST_POLICIES.items()
    } == expected_payloads
    with pytest.raises(TypeError):
        policies.DOCQA_REQUEST_POLICIES["web"] = policies.WEB_REQUEST_POLICY
    with pytest.raises(FrozenInstanceError):
        policies.WEB_REQUEST_POLICY.origin = "cli"


def test_web_builder_applies_web_policy_and_preserves_none_vs_empty_selection():
    policy = _policies().WEB_REQUEST_POLICY

    inherited = build_web_docqa_request(prompt="question", selected_file_ids=None)
    cleared = build_web_docqa_request(prompt="question", selected_file_ids=[])

    assert inherited.qa_scope == policy.qa_scope_default == "page"
    assert inherited.page_number == policy.page_number_default == 1
    assert inherited.controller_mode == policy.controller_mode_default == "llm"
    assert inherited.route_policy == policy.route_policy_default == "auto"
    assert inherited.verification_mode == policy.verification_mode_default == "light"
    assert inherited.origin == policy.origin == "web"
    assert inherited.selected_file_ids is None
    assert cleared.selected_file_ids == []


def test_runtime_turn_copy_preserves_all_canonical_request_fields():
    original = DocQARequest(
        prompt="question",
        controller_question="controller question",
        retrieval_query="retrieval query",
        dataset_family="finance",
        conversation_id="conv-1",
        selected_file_ids=[],
        selected_inputs={9: []},
        qa_scope="document",
        active_file_id="file-1",
        active_file_name="report.pdf",
        page_number=None,
        selected_text="",
        graph_context={"graph": True},
        graph_source_ids=[],
        settings={"reasoning.use": "mara"},
        state={"app": {"regen": False}},
        history=[("old", "answer")],
        max_context_length=16000,
        reasoning_type="mara",
        task_type="analysis",
        agent_mode="auto",
        artifact_type="report",
        note_ids=[],
        controller_mode="llm",
        route_policy="auto",
        planner_backend="heuristic_local",
        planner_model=None,
        allowed_routes=[],
        verification_mode="light",
        verification_domain="finance",
        graph_mode="global",
        visual_retriever_backend="local",
        visual_generator_backend="local",
        page_image_records=[],
        element_index_records=[],
        llm="local",
        use_mindmap=False,
        use_citation="inline",
        language="en",
        command_state="ready",
        user_id="user-1",
        origin="benchmark",
    )
    session = SimpleNamespace(
        conversation_id="conv-1",
        state=original.state,
        messages=original.history,
    )

    copied = _runtime_turn.build_turn_request(
        original,
        session,
        resolved_user_id="user-1",
        selected_inputs={9: []},
        request_file_ids=[],
        load_settings=lambda _user_id: {},
    )

    assert asdict(copied) == asdict(original)


def test_runtime_mara_copy_covers_the_controller_and_multimodal_extensions():
    source = DocQARequest(
        prompt="question",
        controller_question="controller question",
        retrieval_query="retrieval query",
        dataset_family="finance",
        element_index_records=[{"evidence_id": "element-1"}],
    )
    target = DocQARequest(prompt="question")

    _runtime_mara.copy_request_fields(target, source)

    assert target.controller_question == "controller question"
    assert target.retrieval_query == "retrieval query"
    assert target.dataset_family == "finance"
    assert target.element_index_records == [{"evidence_id": "element-1"}]


def test_response_json_and_persisted_session_key_shapes_are_golden():
    response = DocQAResponse(
        conversation_id="conv-1",
        answer="answer",
        references_html="refs",
        references_text="refs",
        mindmap_html="",
        plot=None,
        messages=[("question", "answer")],
        retrieval_messages=["refs"],
        plot_history=[],
        state={"app": {"regen": False}},
        selected_file_ids=[],
        selected_mapping={},
        graph_source_ids=[],
        active_file_id="",
        active_file_name="",
        qa_scope="auto",
        page_number=None,
        selected_text="",
        graph_context={},
        reasoning_id="mara",
        settings={},
        stream_events=[],
    )

    assert tuple(response.as_dict()) == RESPONSE_JSON_KEYS

    data_source = {
        "selected": {},
        "likes": [],
        "chat_suggestions": ["next"],
        "origin": "cli",
        NOTEBOOK_KEY: {
            "notes": [],
            "artifacts": [],
            "selected_source_ids": ["file-1"],
        },
    }
    persisted = _runtime_sessions.build_conversation_data_source(
        data_source=data_source,
        selected_mapping={},
        is_owner=True,
        messages=[("question", "answer")],
        retrieval_history=["refs"],
        plot_history=[],
        state={"app": {"regen": False}},
        graph_source_ids=[],
        origin="web",
    )

    assert set(persisted) == {
        "selected",
        "messages",
        "retrieval_messages",
        "plot_history",
        "state",
        "graph_source_ids",
        "likes",
        "chat_suggestions",
        "origin",
        NOTEBOOK_KEY,
    }
    assert "request" not in persisted
