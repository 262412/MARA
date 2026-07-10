from __future__ import annotations

import os
import subprocess
import sys
import types
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import pytest

from ktem.docqa import DocQARequest as RuntimeDocQARequest
from slide_cli import docqa_request as request_module


CANONICAL_REQUEST_FIELDS = (
    "prompt",
    "controller_question",
    "retrieval_query",
    "dataset_family",
    "conversation_id",
    "selected_file_ids",
    "selected_inputs",
    "qa_scope",
    "active_file_id",
    "active_file_name",
    "page_number",
    "selected_text",
    "graph_context",
    "graph_source_ids",
    "settings",
    "state",
    "history",
    "max_context_length",
    "reasoning_type",
    "task_type",
    "agent_mode",
    "artifact_type",
    "note_ids",
    "controller_mode",
    "route_policy",
    "planner_backend",
    "planner_model",
    "allowed_routes",
    "verification_mode",
    "verification_domain",
    "graph_mode",
    "visual_retriever_backend",
    "visual_generator_backend",
    "page_image_records",
    "element_index_records",
    "llm",
    "use_mindmap",
    "use_citation",
    "language",
    "command_state",
    "user_id",
    "origin",
)

HISTORICAL_FACADE_POSITIONAL_FIELDS = (
    "prompt",
    "conversation_id",
    "selected_file_ids",
    "selected_inputs",
    "qa_scope",
    "active_file_id",
    "active_file_name",
    "page_number",
    "selected_text",
    "graph_context",
    "graph_source_ids",
    "settings",
    "state",
    "history",
    "max_context_length",
    "reasoning_type",
    "task_type",
    "agent_mode",
    "artifact_type",
    "note_ids",
    "controller_mode",
    "route_policy",
    "planner_backend",
    "planner_model",
    "allowed_routes",
    "verification_mode",
    "verification_domain",
    "graph_mode",
    "visual_retriever_backend",
    "visual_generator_backend",
    "page_image_records",
    "llm",
    "use_mindmap",
    "use_citation",
    "language",
    "command_state",
    "user_id",
    "origin",
)

APPENDED_FACADE_FIELDS = (
    "controller_question",
    "retrieval_query",
    "dataset_family",
    "element_index_records",
)


def test_facade_covers_canonical_request_without_breaking_positional_abi():
    runtime_names = tuple(field.name for field in fields(RuntimeDocQARequest))
    facade_names = tuple(field.name for field in fields(request_module.DocQARequest))

    assert runtime_names == CANONICAL_REQUEST_FIELDS
    assert facade_names[:38] == HISTORICAL_FACADE_POSITIONAL_FIELDS
    assert facade_names[38:] == APPENDED_FACADE_FIELDS
    assert set(facade_names) == set(runtime_names)


def test_facade_defaults_match_canonical_defaults_for_all_42_fields():
    facade_defaults = asdict(request_module.DocQARequest(prompt="question"))
    runtime_defaults = asdict(RuntimeDocQARequest(prompt="question"))

    assert facade_defaults == runtime_defaults


def test_facade_conversion_explicitly_round_trips_every_field():
    payload = {
        name: f"sentinel-{index}-{name}"
        for index, name in enumerate(CANONICAL_REQUEST_FIELDS)
    }
    facade = request_module.DocQARequest(**payload)

    runtime_request = request_module.to_runtime_docqa_request(facade)

    assert asdict(runtime_request) == payload


def test_facade_conversion_fails_loudly_when_runtime_contract_drifts(monkeypatch):
    @dataclass
    class DriftedRuntimeRequest:
        prompt: str

    fake_docqa = types.ModuleType("ktem.docqa")
    fake_docqa.DocQARequest = DriftedRuntimeRequest
    monkeypatch.setitem(sys.modules, "ktem.docqa", fake_docqa)

    with pytest.raises(
        request_module.DocQARequestContractError,
        match="missing=.*controller_question",
    ):
        request_module.to_runtime_docqa_request(
            request_module.DocQARequest(prompt="question")
        )


def test_constructing_facade_does_not_import_ktem_docqa():
    package_root = Path(__file__).resolve().parents[1]
    script = """
import sys
from slide_cli.docqa_request import DocQARequest
request = DocQARequest('question')
assert request.prompt == 'question'
assert 'ktem.docqa' not in sys.modules
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(package_root)

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr
