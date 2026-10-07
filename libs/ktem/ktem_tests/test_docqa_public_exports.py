"""Fixed public contracts captured before the DocQA facade becomes lazy."""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
import pickle
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest
from ktem_tests.docqa_import_test_helpers import run_docqa_import_probe

CONTRACT = json.loads(
    (Path(__file__).parent / "fixtures/docqa_public_exports.json").read_text(
        encoding="utf-8"
    )
)
DATA_SAMPLES = {
    "DocQARequest": {"prompt": "Which page?", "selected_file_ids": ["file-1"]},
    "DocQAResponse": {
        "conversation_id": "session-1",
        "answer": "Page 2.",
        "references_html": "<p>Source</p>",
        "references_text": "Source",
        "mindmap_html": "",
        "plot": None,
        "messages": [("Which page?", "Page 2.")],
        "retrieval_messages": ["Source"],
        "plot_history": [],
        "state": {"turn": 1},
        "selected_file_ids": ["file-1"],
        "selected_mapping": {"1": ["file-1"]},
        "graph_source_ids": ["source-1"],
        "active_file_id": "file-1",
        "active_file_name": "report.pdf",
        "qa_scope": "selected",
        "page_number": 2,
        "selected_text": "Source",
        "graph_context": {},
        "reasoning_id": "simple",
        "settings": {},
        "stream_events": [{"kind": "answer"}],
    },
    "DocQATurnUpdate": {"answer": "Page 2.", "event": {"kind": "answer"}},
    "DocQASession": {
        "conversation_id": "session-1",
        "name": "Example",
        "user_id": "owner",
        "is_public": False,
        "data_source": {"1": ["file-1"]},
        "messages": [("Question", "Answer")],
        "retrieval_messages": [],
        "plot_history": [],
        "state": {},
        "selected_mapping": {},
        "graph_source_ids": [],
        "origin": "cli",
        "date_created": "2026-01-02",
        "date_updated": "2026-01-03",
    },
    "DocQASessionSummary": {
        "conversation_id": "session-1",
        "name": "Example",
        "message_count": 1,
        "graph_source_count": 0,
        "origin": "cli",
        "is_public": False,
        "date_created": "2026-01-02",
        "date_updated": "2026-01-03",
    },
    "DocQAFileRecord": {
        "file_id": "file-1",
        "name": "report.pdf",
        "size": 123,
        "tokens": 12,
        "loader": "pdf",
        "path": "owned/report.pdf",
        "date_created": "2026-01-02",
    },
    "DocQAIndexResult": {
        "successes": [{"id": "file-1"}],
        "failures": [],
        "debug_messages": [],
    },
    "DocQADoctorResult": {
        "ok": True,
        "app_name": "Test",
        "default_user_id": "owner",
        "index_name": "Files",
        "index_id": 1,
        "llm_default": "",
        "embedding_default": "",
        "file_count": 1,
        "session_count": 1,
        "graph_cache_dir": "owned/graph",
        "issues": [],
    },
}


def _json_value(value):
    def encode(item):
        if isinstance(item, Mapping):
            return dict(item)
        return dataclasses.asdict(item)

    return json.loads(json.dumps(value, default=encode))


def test_export_order_and_discovery_preserve_the_fixed_contract():
    import ktem.docqa as docqa

    assert docqa.__all__ == CONTRACT["all"]
    assert set(CONTRACT["all"] + CONTRACT["legacy_submodules"]) <= set(dir(docqa))
    with pytest.raises(AttributeError, match="not_a_docqa_export"):
        getattr(docqa, "not_a_docqa_export")


@pytest.mark.parametrize("name", CONTRACT["all"])
def test_exports_keep_identity_signatures_defaults_and_constants(name):
    import ktem.docqa as docqa

    value = getattr(docqa, name)
    source, attribute = CONTRACT["sources"][name]
    module = importlib.import_module(source)
    assert value is (getattr(module, attribute) if attribute else module)
    assert getattr(docqa, name) is value
    expected = CONTRACT["exports"][name]
    assert (
        value.__name__
        if isinstance(value, ModuleType)
        else getattr(value, "__module__", None)
    ) == expected["module"]
    if "signature" in expected:
        assert str(inspect.signature(value)) == expected["signature"]
    if "value" in expected:
        assert _json_value(value) == expected["value"]
    if "factories" in expected:
        factories = {
            field.name: field.default_factory.__module__
            + "."
            + getattr(field.default_factory, "__qualname__")
            for field in dataclasses.fields(value)
            if field.default_factory is not dataclasses.MISSING
        }
        assert factories == expected["factories"]


@pytest.mark.parametrize("name", CONTRACT["legacy_submodules"])
def test_previously_bound_submodules_remain_accessible(name):
    import ktem.docqa as docqa

    assert getattr(docqa, name) is importlib.import_module("ktem.docqa." + name)


@pytest.mark.parametrize("name, arguments", DATA_SAMPLES.items())
def test_original_data_classes_and_owned_serialization_roundtrips(name, arguments):
    import ktem.docqa as docqa
    from ktem.docqa import _runtime_models, runtime

    public = getattr(docqa, name)
    original = getattr(_runtime_models, name)
    assert public is original is getattr(runtime, name)
    first, second = public(**arguments), original(**arguments)
    assert dataclasses.asdict(first) == dataclasses.asdict(second)
    restored = pickle.loads(pickle.dumps(first))
    assert type(restored) is public
    assert restored == first
    if hasattr(first, "as_dict"):
        assert _json_value(first.as_dict()) == _json_value(second.as_dict())
    for field in dataclasses.fields(public):
        if (
            field.default_factory is not dataclasses.MISSING
            and field.name not in arguments
        ):
            assert getattr(first, field.name) is not getattr(second, field.name)


@pytest.mark.parametrize(
    "first_import",
    [
        "import ktem.docqa as facade",
        "from ktem.docqa import DocQARequest",
        "import ktem.docqa._runtime_models",
        "import ktem.docqa.runtime",
        "import ktem.docqa.execution",
    ],
)
def test_real_import_orders_keep_original_objects(first_import):
    run_docqa_import_probe(
        first_import
        + """
import ktem.docqa as facade
from ktem.docqa import _runtime_models, runtime, execution
assert facade.DocQARequest is _runtime_models.DocQARequest is runtime.DocQARequest
assert facade.DocQAResponse is _runtime_models.DocQAResponse is runtime.DocQAResponse
assert facade.DocQARuntime is runtime.DocQARuntime
assert facade.execute_controller_turn is execution.execute_controller_turn
from sqlalchemy import inspect as inspect_database
from ktem.db.models import User, engine
assert Path(engine.url.database).resolve().is_relative_to(owned_root)
assert inspect_database(engine).has_table(User.__tablename__)
from ktem.llms.manager import llms
from ktem.embeddings.manager import embedding_models_manager
from ktem.rerankings.manager import reranking_models_manager
assert llms._manager is None
assert embedding_models_manager._manager is None
assert reranking_models_manager._manager is None
"""
    )


def test_star_import_preserves_all_exports_and_loads_the_real_runtime():
    run_docqa_import_probe(
        """
namespace = {}
exec('from ktem.docqa import *', namespace)
import ktem.docqa as facade
assert set(namespace) - {'__builtins__'} == set(facade.__all__)
assert all(namespace[name] is getattr(facade, name) for name in facade.__all__)
assert 'ktem.docqa.runtime' in sys.modules
assert 'ktem.docqa.execution' in sys.modules
"""
    )


def test_dotted_import_and_legacy_patch_reach_the_real_runtime_consumer():
    run_docqa_import_probe(
        """
from unittest.mock import patch
from theflow.utils.modules import import_dotted_string
import ktem.docqa as facade
from ktem.docqa.runtime import DocQARuntime
assert import_dotted_string('ktem.docqa.DocQARuntime', safe=False) is DocQARuntime
assert import_dotted_string('ktem.docqa.DocQARequest', safe=False) is facade.DocQARequest
with patch('ktem.docqa._runtime_selection.normalize_selected_file_ids', return_value=['patched']) as mock:
    assert DocQARuntime._normalize_selected_file_ids(['source']) == ['patched']
    mock.assert_called_once_with(['source'])
with patch('ktem.docqa.runtime.DeletionCoordinator') as coordinator:
    assert facade.runtime.DeletionCoordinator is coordinator
"""
    )
