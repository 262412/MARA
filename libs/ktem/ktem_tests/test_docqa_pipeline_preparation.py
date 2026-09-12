"""Fixed expectations established before extracting the preparation flow."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import ktem.docqa.runtime as runtime_module
import pytest
from ktem.docqa._runtime_models import DocQARequest, _PreparedPipeline
from ktem.preview.errors import PreviewContextError, PreviewErrorCode
from ktem_tests.pipeline_preparation_test_helpers import PreparationProbe

FULL_TRACE = [
    "resolve_user",
    "load_settings",
    "get_info",
    "overrides",
    "retriever:9",
    "retriever:4",
    "reasoning_state",
    "get_pipeline",
    "selected_ids",
    "active_source",
    "infer_source",
    "normalize_page",
    "normalize_scope",
    "page_text",
    "read_page",
    "selected_records",
    "sources",
    "page_images",
    "normalize_graph",
    "validate_graph",
    "sources",
    "multimodal",
    "local_elements",
    "local_graph",
    "request_elements",
    "request_context",
]


@pytest.fixture
def probe(monkeypatch):
    return PreparationProbe(monkeypatch)


def request(**overrides):
    values: dict[str, Any] = dict(
        prompt="Question",
        user_id="requested-user",
        qa_scope="page",
        page_number="2",
        selected_inputs={9: ["chosen-b", "chosen-a"], 4: {"nested": ["other"]}},
        graph_source_ids=["graph-1"],
        graph_context={"custom": {"values": ["context"]}},
    )
    values.update(overrides)
    return DocQARequest(**values)


def test_fixed_order_values_and_original_prepared_type(probe):
    req = request(state={"app": {"regen": True}, "mara": {"values": ["state"]}})
    prepared = probe.prepare(req)
    assert probe.names == FULL_TRACE
    assert type(prepared) is _PreparedPipeline
    assert type(prepared).__module__ == "ktem.docqa._runtime_models"
    assert [field.name for field in fields(_PreparedPipeline)] == [
        "pipeline",
        "reasoning_state",
        "selected_file_ids",
        "active_file_id",
        "active_file_name",
        "qa_scope",
        "page_number",
        "selected_text",
        "graph_context",
        "settings",
        "reasoning_id",
    ]
    assert vars(prepared) == dict(
        pipeline=probe.pipeline,
        reasoning_state={"app": {"regen": True}, "pipeline": {"values": ["state"]}},
        selected_file_ids=["file-b", "file-a"],
        active_file_id="file-b",
        active_file_name="Report.PDF",
        qa_scope="page",
        page_number=2,
        selected_text="Page context",
        graph_context={**req.graph_context, **probe.local_graph},
        settings=prepared.settings,
        reasoning_id="mara",
    )
    assert probe.call("resolve_user")[1] == ("requested-user",)
    assert probe.call("load_settings")[1] == ("principal",)
    assert probe.call("get_pipeline")[1][2] == probe.retrievers
    assert probe.call("selected_ids")[1] == ("principal", req.selected_inputs[9])
    assert probe.pipeline.selected_file_records == [
        {"file_id": "file-b", "file_name": "Report.PDF", "path": "/owned/source"},
        {"file_id": "file-a", "file_name": "Report.PDF", "path": "/owned/source"},
    ]
    for name, _args, kwargs in probe.calls:
        if name in {"infer_source", "read_page", "sources"}:
            assert kwargs["user_id"] == "principal"
        if name == "sources":
            assert kwargs["strict"] is True


@pytest.mark.parametrize(
    "settings", [None, {}, {"reasoning.use": "mara", "nested": {"v": [1]}}]
)
@pytest.mark.parametrize(
    "state", [None, {}, {"app": {"regen": True}, "mara": {"v": [2]}}]
)
def test_settings_and_state_fallbacks_are_deep_copied(probe, settings, state):
    req = request(settings=settings, state=state)
    source_settings = settings or probe.settings
    original_settings, original_state = deepcopy(source_settings), deepcopy(state)
    prepared = probe.prepare(req)
    assert probe.counts["load_settings"] == (0 if settings else 1)
    assert prepared.settings is not source_settings
    prepared.settings["nested"][next(iter(source_settings["nested"]))].append("changed")
    assert source_settings == original_settings
    copied_state = probe.call("reasoning_state")[1][0]
    assert copied_state == (state or {"app": {"regen": False}})
    assert copied_state is not state
    prepared.reasoning_state["app"]["regen"] = "changed"
    if state:
        prepared.reasoning_state["pipeline"]["v"].append(3)
        assert copied_state["mara"]["v"] == [2]
    assert state == original_state


@pytest.mark.parametrize("selected_inputs", [None, {}, {9: ["raw"], 4: {"v": [1]}}])
def test_selected_inputs_keep_shallow_values_and_index_order(probe, selected_inputs):
    probe.prepare(request(selected_inputs=selected_inputs))
    for index_id in (9, 4):
        args = probe.call(f"retriever:{index_id}")[1]
        assert args[1] == "principal"
        assert args[2] is (selected_inputs or {}).get(index_id)
    assert probe.call("retriever:9")[1][0] is probe.call("retriever:4")[1][0]
    assert probe.names.index("retriever:9") < probe.names.index("retriever:4")


@pytest.mark.parametrize("mode", [None, "(default)", "mara"])
def test_default_and_explicit_reasoning(probe, mode):
    assert probe.prepare(request(reasoning_type=mode)).reasoning_id == "mara"
    assert probe.counts["get_info"] == probe.counts["get_pipeline"] == 1


@pytest.mark.parametrize("mode", ["", "missing"])
def test_unknown_reasoning_fails_before_later_resources(probe, mode):
    del probe.runtime._app
    del probe.runtime.file_index
    with pytest.raises(ValueError) as caught:
        probe.prepare(request(reasoning_type=mode))
    assert str(caught.value) == f"Unknown reasoning pipeline '{mode}'."
    assert probe.names == ["resolve_user", "load_settings"]


def test_missing_default_reasoning_key_fails_at_original_stage(probe):
    with pytest.raises(KeyError) as caught:
        probe.prepare(request(settings={"unrelated": True}))
    assert caught.value.args == ("reasoning.use",)
    assert probe.names == ["resolve_user"]


def test_empty_reasoning_name_is_used_when_registered(probe, monkeypatch):
    monkeypatch.setitem(runtime_module.reasonings, "", probe.reasoning)
    assert probe.prepare(request(reasoning_type="")).reasoning_id == "mara"


@pytest.mark.parametrize("origin", ["cli", "benchmark", " Benchmark "])
def test_real_setting_overrides_precede_retriever_and_pipeline(probe, origin):
    prepared = probe.prepare(
        request(
            origin=origin,
            llm="request-model",
            use_mindmap=False,
            use_citation=True,
            language="zh",
            max_context_length="2048",
        )
    )
    settings = prepared.settings
    assert settings["reasoning.options.mara.llm"] == "request-model"
    assert settings["reasoning.options.simple.create_mindmap"] is False
    assert settings["reasoning.options.simple.highlight_citation"] is True
    assert settings["reasoning.lang"] == "zh"
    assert settings["reasoning.max_context_length"] == 2048
    expected_prompt = (
        "Saved prompt  "
        if origin.strip().lower() == "benchmark"
        else ("Saved prompt" + runtime_module._pipeline.STRUCTURED_QA_PROMPT_GUARD)
    )
    assert settings["reasoning.options.mara.qa_prompt"] == expected_prompt
    assert probe.call("retriever:9")[1][0] is settings
    assert probe.call("get_pipeline")[1][0] is settings


def test_invalid_override_short_circuits_before_app_lookup(probe):
    del probe.runtime._app
    with pytest.raises(ValueError, match="invalid literal"):
        probe.prepare(request(max_context_length="invalid"))
    assert probe.names == FULL_TRACE[:4]


def test_web_search_replaces_retrievers_but_keeps_later_file_work(probe):
    del probe.runtime._app
    probe.prepare(request(command_state=runtime_module.WEB_SEARCH_COMMAND))
    assert probe.names == FULL_TRACE[:4] + ["web_search"] + FULL_TRACE[6:]
    assert probe.call("get_pipeline")[1][2] == [probe.web_retriever]


def test_missing_web_backend_fails_after_overrides(probe):
    probe.runtime._web_search_cls = None
    with pytest.raises(ValueError, match=r"^Web search back-end is not available\.$"):
        probe.prepare(request(command_state=runtime_module.WEB_SEARCH_COMMAND))
    assert probe.names == FULL_TRACE[:4]


def test_no_index_collection_still_creates_pipeline(probe):
    del probe.runtime._app.index_manager.indices
    probe.prepare(request())
    assert probe.call("get_pipeline")[1][2] == []
    assert "selected_ids" in probe.names


@pytest.mark.parametrize(
    "scope,name,page,text,expected_page",
    [
        ("document", "report.pdf", 3, "  selected  ", None),
        ("page", "report.pdf", "3", "  selected  ", 3),
        ("page", "report.txt", 3, "  selected  ", None),
        ("page", "report.pdf", None, "selected", None),
        ("whole-document", "report.pdf", 3, "selected", None),
        ("multi-doc", "report.pdf", 3, "selected", None),
        ("auto", "report.pdf", 3, "selected", 3),
    ],
)
def test_page_scope_and_selected_text_combinations(
    probe, scope, name, page, text, expected_page
):
    prepared = probe.prepare(
        request(
            qa_scope=scope, active_file_name=name, page_number=page, selected_text=text
        )
    )
    assert prepared.page_number == expected_page
    assert prepared.selected_text == text.strip()
    assert "read_page" not in probe.names
    assert prepared.pipeline.page_number == expected_page


@pytest.mark.parametrize(
    "file_id,file_name,expected_id,expected_name,event",
    [
        ("chosen", "Known.pdf", "chosen", "Known.pdf", None),
        ("chosen", "", "chosen", "Report.PDF", "file_name"),
        ("", "Known.pdf", "", "Known.pdf", None),
        ("", "", "file-b", "Report.PDF", "infer_source"),
    ],
)
def test_active_source_precedence(
    probe, file_id, file_name, expected_id, expected_name, event
):
    prepared = probe.prepare(
        request(
            active_file_id=file_id, active_file_name=file_name, selected_text="text"
        )
    )
    assert (prepared.active_file_id, prepared.active_file_name) == (
        expected_id,
        expected_name,
    )
    assert [name for name in probe.names if name in {"file_name", "infer_source"}] == (
        [event] if event else []
    )


def test_no_file_index_retains_explicit_context_and_runs_later_helpers(probe):
    probe.runtime.file_index = None
    prepared = probe.prepare(
        request(
            active_file_id="explicit",
            active_file_name="Known.pdf",
            selected_text="text",
        )
    )
    assert prepared.selected_file_ids == []
    assert prepared.active_file_id == "explicit"
    assert "selected_ids" not in probe.names and "active_source" not in probe.names
    assert probe.call("local_elements")[1] == (None, ["explicit"])
    assert probe.call("local_graph")[1] == (None, ["graph-1"])


def test_empty_page_text_keeps_typed_error_and_post_factory_short_circuit(probe):
    probe.page_text = ""
    with pytest.raises(PreviewContextError) as caught:
        probe.prepare(request())
    assert caught.value.code == PreviewErrorCode.CONTEXT_TEXT_UNAVAILABLE
    assert caught.value.stage == "page_context"
    assert probe.names == FULL_TRACE[:15]
    assert vars(probe.pipeline) == {}


@pytest.mark.parametrize(
    "stage,occurrence",
    [
        ("resolve_user", 1),
        ("load_settings", 1),
        ("get_info", 1),
        ("overrides", 1),
        ("retriever:9", 1),
        ("retriever:4", 1),
        ("reasoning_state", 1),
        ("get_pipeline", 1),
        ("selected_ids", 1),
        ("active_source", 1),
        ("normalize_page", 1),
        ("normalize_scope", 1),
        ("page_text", 1),
        ("sources", 1),
        ("page_images", 1),
        ("normalize_graph", 1),
        ("validate_graph", 1),
        ("sources", 2),
        ("multimodal", 1),
        ("local_elements", 1),
        ("local_graph", 1),
        ("request_elements", 1),
        ("request_context", 1),
    ],
)
def test_resource_errors_propagate_unchanged_and_stop_at_original_stage(
    probe, stage, occurrence
):
    probe.fail_at = (stage, occurrence)
    with pytest.raises(RuntimeError) as caught:
        probe.prepare(request())
    assert caught.value is probe.failure
    position = [i for i, name in enumerate(FULL_TRACE) if name == stage][occurrence - 1]
    assert probe.names == FULL_TRACE[: position + 1]


def test_graph_priority_record_copies_and_request_context_references(probe):
    graph = {"graph_index": {"nodes": ["request"]}, "custom": [1]}
    page_record = {"file_id": "file-b", "page_label": "2", "extra": {"v": [1]}}
    extra = probe.element("request", "Request element")
    req = request(
        graph_context=graph,
        page_image_records=[page_record, "invalid"],
        element_index_records=[extra],
        selected_file_ids=["request-only"],
        controller_question="  control  ",
        retrieval_query="  retrieve  ",
    )
    prepared = probe.prepare(req)
    assert prepared.graph_context is graph is probe.pipeline.graph_context
    assert "local_graph" not in probe.names
    assert prepared.selected_file_ids is probe.resolved_ids
    assert prepared.reasoning_state is probe.call("get_pipeline")[1][1]
    assert prepared.settings is probe.call("get_pipeline")[1][0]
    assert probe.pipeline.page_image_index_records == [page_record]
    assert probe.pipeline.page_image_index_records[0] is not page_record
    assert probe.pipeline.page_image_index_records[0]["extra"] is page_record["extra"]
    assert [item["element_id"] for item in probe.pipeline.element_index_records] == [
        "local",
        "request",
    ]
    assert probe.pipeline.element_ingestion_trace == {
        "element_ingestion_status": "complete",
        "accepted_record_count": 2,
        "rejected_record_count": 0,
        "identity_conflict_count": 0,
        "identity_conflicts": [],
    }
    assert probe.pipeline.docqa_request is req
    assert probe.pipeline.controller_question == "control"
    assert probe.pipeline.retrieval_query == "retrieve"
    assert probe.pipeline.selected_file_ids == ["request-only"]
    assert probe.pipeline.selected_file_ids is not req.selected_file_ids


@pytest.mark.parametrize("context", [None, [], {}])
def test_graph_fallback_and_empty_request_records(probe, context):
    prepared = probe.prepare(request(graph_context=context, graph_source_ids=[]))
    assert prepared.graph_context == probe.local_graph
    assert probe.call("local_graph")[1][1] == ["file-b", "file-a"]
    assert probe.pipeline.element_index_records is probe.local_elements
    assert not hasattr(probe.pipeline, "element_ingestion_trace")
    assert not hasattr(probe.pipeline, "page_image_index_records")


def test_create_pipeline_consumes_overridden_preparation_entry(probe, monkeypatch):
    expected = SimpleNamespace(pipeline=object(), reasoning_state={"kept": object()})
    seen = []

    def prepare(req):
        seen.append(req)
        return expected

    monkeypatch.setattr(probe.runtime, "_prepare_pipeline", prepare)
    req = request()
    result = probe.runtime.create_pipeline(req)
    assert result == (expected.pipeline, expected.reasoning_state)
    assert result[0] is expected.pipeline and result[1] is expected.reasoning_state
    assert seen == [req] and probe.names == []


def test_selected_input_container_is_copied_before_index_callbacks(probe, monkeypatch):
    req = request()
    previous = req.selected_inputs[4]
    original = probe.file_index.get_retriever_pipelines

    def first(settings, user_id, selected_input):
        req.selected_inputs[4] = {"replacement": True}
        selected_input.append("shared-nested-value")
        return original(settings, user_id, selected_input)

    monkeypatch.setattr(probe.file_index, "get_retriever_pipelines", first)
    probe.prepare(req)
    assert probe.call("retriever:4")[1][2] is previous
    assert req.selected_inputs[9][-1] == "shared-nested-value"


@pytest.mark.parametrize("field", ["settings", "state"])
def test_deepcopy_failures_precede_reasoning_and_keep_exception_identity(probe, field):
    class CannotCopy:
        def __deepcopy__(self, _memo):
            raise probe.failure

    with pytest.raises(RuntimeError) as caught:
        probe.prepare(request(**{field: {"bad": CannotCopy()}}))
    assert caught.value is probe.failure
    assert probe.names == (["resolve_user"] if field == "settings" else FULL_TRACE[:2])


def test_invalid_selected_inputs_fail_before_reasoning(probe):
    with pytest.raises(TypeError, match="not iterable"):
        probe.prepare(request(selected_inputs=42))
    assert probe.names == FULL_TRACE[:2]


def test_invalid_state_fails_after_retriever_creation(probe):
    with pytest.raises(AttributeError, match="has no attribute 'get'"):
        probe.prepare(request(state=["invalid"]))
    assert probe.names == FULL_TRACE[:7]


def test_unknown_scope_fails_after_pipeline_and_page_normalization(probe):
    with pytest.raises(ValueError) as caught:
        probe.prepare(request(qa_scope="current_page"))
    assert str(caught.value) == (
        "Unknown QA scope 'current_page'. Expected page, document, multi-document, or auto."
    )
    assert probe.names == FULL_TRACE[:13]


def test_factory_can_supply_later_resources_and_patch_points(probe, monkeypatch):
    original = probe.reasoning.get_pipeline
    original_images = runtime_module._apply_request_page_image_records
    del probe.runtime.file_index
    del probe.runtime._preview

    def get_pipeline(settings, state, retrievers):
        result = original(settings, state, retrievers)
        probe.runtime.file_index = probe.file_index
        probe.runtime._preview = probe.preview
        monkeypatch.setattr(probe.runtime, "_normalize_page_number", lambda _value: 7)
        monkeypatch.setattr(runtime_module, "_apply_request_page_image_records", images)
        return result

    def images(pipeline, req):
        pipeline.late_image_patch = True
        original_images(pipeline, req)

    monkeypatch.setattr(probe.reasoning, "get_pipeline", get_pipeline)
    prepared = probe.prepare(request())
    assert prepared.page_number == 7
    assert probe.pipeline.late_image_patch is True
    assert "normalize_page" not in probe.names


def test_reasoning_registry_is_looked_up_again_after_membership(probe, monkeypatch):
    class Registry(dict):
        def __contains__(self, key):
            monkeypatch.setattr(runtime_module, "reasonings", {"mara": probe.reasoning})
            return super().__contains__(key)

    monkeypatch.setattr(runtime_module, "reasonings", Registry(mara=object()))
    assert probe.prepare(request()).reasoning_id == "mara"


def test_empty_request_state_keeps_original_literal_default(probe, monkeypatch):
    monkeypatch.setattr(
        runtime_module._pipeline, "STATE", {"app": {"regen": "different"}}
    )
    prepared = probe.prepare(request(state={}))
    assert prepared.reasoning_state == {"app": {"regen": False}, "pipeline": {}}


def test_identity_deduplication_and_invalid_records_keep_original_trace(probe):
    duplicate = dict(probe.local_elements[0], score=0.9)
    req = request(element_index_records=[duplicate, {}, "invalid"])
    probe.prepare(req)
    assert len(probe.pipeline.element_index_records) == 1
    assert probe.pipeline.element_index_records[0]["element_id"] == "local"
    assert probe.pipeline.element_index_records[0]["score"] == 0.9
    assert "score" not in probe.local_elements[0]
    assert probe.pipeline.element_ingestion_trace == {
        "element_ingestion_status": "complete",
        "accepted_record_count": 1,
        "rejected_record_count": 0,
        "identity_conflict_count": 0,
        "identity_conflicts": [],
    }


def test_identity_conflict_is_filtered_and_reported_without_aborting_preparation(probe):
    local = probe.local_elements[0]
    local.update(
        source_id="file-b",
        cell_id="physical-cell",
        row_index=1,
        column_index=1,
        value="10",
        text="Revenue 10",
    )
    conflict = dict(local, row_index=2, value="20", text="Revenue 20")
    req = request(element_index_records=[conflict])
    probe.prepare(req)
    assert len(probe.pipeline.element_index_records) == 1
    assert probe.pipeline.element_index_records[0]["value"] == "10"
    trace = probe.pipeline.element_ingestion_trace
    assert trace["element_ingestion_status"] == "partial"
    assert (
        trace["accepted_record_count"],
        trace["rejected_record_count"],
        trace["identity_conflict_count"],
    ) == (1, 1, 1)
    assert (
        trace["identity_conflicts"][0]["derived_identity"]
        == "cell:file-b:physical-cell"
    )
    assert set(trace["identity_conflicts"][0]["conflicting_fields"]) == {
        "row_index",
        "value",
    }
    assert probe.pipeline.docqa_request is req
    assert probe.names[-1] == "request_context"


def test_runtime_and_prepared_model_come_from_the_current_source_tree():
    package = Path(__file__).resolve().parents[1] / "ktem"
    assert Path(runtime_module.__file__).resolve() == package / "docqa/runtime.py"
    assert runtime_module._PreparedPipeline is _PreparedPipeline
