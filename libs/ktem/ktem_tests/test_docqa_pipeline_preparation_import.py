"""Exercise preparation with explicit capabilities and the real cold parent."""

from __future__ import annotations

from ktem_tests.docqa_import_test_helpers import run_docqa_import_probe

PREPARATION_PROBE_SOURCE = """
from types import SimpleNamespace

from ktem.docqa import pipeline_preparation
from ktem.docqa._runtime_models import DocQARequest, _PreparedPipeline
from ktem.docqa._runtime_pipeline import apply_request_setting_overrides, build_reasoning_state
from ktem.docqa._runtime_selection import (
    normalize_page_number, normalize_qa_scope, normalize_selected_file_ids,
)

assert Path(pipeline_preparation.__file__).parent == Path(ktem.__file__).parent / 'docqa'
assert 'ktem.docqa.runtime' not in sys.modules
calls = []
pipeline = SimpleNamespace()

class Reasoning:
    @staticmethod
    def get_info():
        calls.append('get_info')
        return {'id': 'cold'}

    @staticmethod
    def get_pipeline(settings, state, retrievers):
        calls.append('get_pipeline')
        assert settings['reasoning.use'] == 'cold'
        assert state == {'app': {'regen': False}, 'pipeline': {}}
        assert retrievers == []
        return pipeline

deps = pipeline_preparation.PipelinePreparationDependencies(
    resolve_user_id=lambda user: user,
    load_settings=lambda user: {'reasoning.use': 'cold'},
    get_reasonings=lambda: {'cold': Reasoning}, get_indices=lambda: [],
    get_web_search_class=lambda: None, get_file_index=lambda: None,
    get_preview=lambda: None, normalize_page_number=normalize_page_number,
    normalize_qa_scope=normalize_qa_scope,
    normalize_selected_file_ids=normalize_selected_file_ids,
    selected_file_records=lambda ids, active, user: [],
    apply_setting_overrides=apply_request_setting_overrides,
    build_reasoning_state=build_reasoning_state,
    apply_page_image_records=lambda p, r: calls.append('images'),
    apply_multimodal_indexes=lambda p, i, ids, active, graph_ids, context: context,
    apply_element_records=lambda p, r: calls.append('elements'),
    apply_request_context=lambda p, r, g: setattr(p, 'docqa_request', r),
)
request = DocQARequest(prompt='Cold preparation', user_id='owner', qa_scope='document')
prepared = pipeline_preparation.prepare_pipeline(
    request, dependencies=deps, default_state={'app': {'regen': False}},
    web_search_command='web',
)
assert type(prepared) is _PreparedPipeline
assert prepared.__class__.__module__ == 'ktem.docqa._runtime_models'
assert prepared.pipeline is pipeline and pipeline.docqa_request is request
assert prepared.selected_file_ids == [] and prepared.qa_scope == 'document'
assert prepared.page_number is None and prepared.selected_text == ''
assert prepared.graph_context is request.graph_context
assert calls == ['get_info', 'get_pipeline', 'images', 'elements']
"""


def test_preparation_import_and_independent_call_do_not_load_runtime_services():
    result = run_docqa_import_probe(PREPARATION_PROBE_SOURCE)
    blocked = (
        "ktem.docqa.runtime",
        "ktem.docqa._runtime_app",
        "ktem.docqa._runtime_notebook",
        "ktem.docqa._runtime_session_service",
        "ktem.docqa._runtime_file_service",
        "ktem.db",
        "ktem.index",
        "ktem.llms",
        "ktem.embeddings",
        "ktem.rerankings",
        "ktem.components",
        "sqlmodel",
        "sqlalchemy",
        "gradio",
    )
    assert not any(
        name == prefix or name.startswith(prefix + ".")
        for name in result["added_modules"]
        for prefix in blocked
    ), result["added_modules"]
    assert result["added_events"] == []
