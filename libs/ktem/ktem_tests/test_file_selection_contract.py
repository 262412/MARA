from __future__ import annotations

import importlib
import inspect
from types import SimpleNamespace

import pytest

LEGACY_MODULES = (
    "ktem.docqa._runtime_selection",
    "ktem.pages.chat.source_scope",
)
STATIC_CONSUMERS = (
    ("ktem.docqa.runtime", "DocQARuntime", "ktem.docqa._runtime_selection"),
    ("ktem.pages.chat", "ChatPage", "ktem.pages.chat"),
)


@pytest.fixture(
    params=(
        (LEGACY_MODULES[0], None),
        (LEGACY_MODULES[1], None),
        ("ktem.docqa.runtime", "DocQARuntime"),
        ("ktem.pages.chat", "ChatPage"),
    ),
    ids=("docqa-module", "chat-module", "docqa-static", "chat-static"),
)
def selection_api(request):
    module_name, class_name = request.param
    module = importlib.import_module(module_name)
    if class_name is None:
        return module
    owner = getattr(module, class_name)
    return SimpleNamespace(
        normalize_selected_file_ids=owner._normalize_selected_file_ids,
        merge_unique_file_ids=owner._merge_unique_file_ids,
    )


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        ("", []),
        ([], []),
        (0, ["0"]),
        (False, ["False"]),
        ("  ", ["  "]),
        (" file-1 ", [" file-1 "]),
        (["a", "a", None, "", " b ", 0, False], ["a", "a", " b ", "0", "False"]),
        (("a", "b"), ["('a', 'b')"]),
        ((), ["()"]),
        ([[], ["a", "b"], (), {"id": "x"}], ["[]", "['a', 'b']", "()", "{'id': 'x'}"]),
        ({"id": "x"}, ["{'id': 'x'}"]),
        ([1, True], ["1", "True"]),
        (["select", "upload", "all"], ["select", "upload", "all"]),
    ],
)
def test_normalize_preserves_fixed_legacy_values(selection_api, value, expected):
    assert selection_api.normalize_selected_file_ids(value) == expected


@pytest.mark.parametrize(
    "groups, expected",
    [
        ((), []),
        ((None, "", [], False, 0, (), {}), []),
        ((" file-1 ",), ["file-1"]),
        ((" a ", ["a", " b ", "", "  ", None, 0, False, "b"], " c "), ["a", "b", "c"]),
        ((["b", "a", "b"], ["c", "a"], "b"), ["b", "a", "c"]),
        (([1, "1", True, "True", False, 0, "0"],), ["1", "True", "0"]),
        ((("a", " b "),), ["('a', ' b ')"]),
        (
            ([["a", "b"], ["a", "b"], [], [False], {"id": "x"}],),
            ["['a', 'b']", "[False]", "{'id': 'x'}"],
        ),
        (([" select ", "upload", "all"],), ["select", "upload", "all"]),
        ((["A", "a", " A "],), ["A", "a"]),
    ],
)
def test_merge_preserves_fixed_legacy_values(selection_api, groups, expected):
    assert selection_api.merge_unique_file_ids(*groups) == expected


def test_selection_results_are_fresh_and_inputs_are_unchanged(selection_api):
    values = [" a ", "a", None, 0, False]
    normalized = selection_api.normalize_selected_file_ids(values)
    merged = selection_api.merge_unique_file_ids(values)
    normalized.append("new")
    merged.append("new")

    assert values == [" a ", "a", None, 0, False]
    assert selection_api.normalize_selected_file_ids(values) == [
        " a ",
        "a",
        "0",
        "False",
    ]
    assert selection_api.merge_unique_file_ids(values) == ["a"]


class _BadString:
    def __str__(self):
        raise ValueError("cannot convert file id")


class _BadEquality:
    def __eq__(self, _other):
        raise TypeError("file id comparison failed")


class _BadTruth:
    def __bool__(self):
        raise RuntimeError("file id truth check failed")

    def __str__(self):
        return "file-value"


@pytest.mark.parametrize(
    "operation", ["normalize_selected_file_ids", "merge_unique_file_ids"]
)
@pytest.mark.parametrize("as_list", [False, True])
def test_string_conversion_errors_propagate(selection_api, operation, as_list):
    value = [_BadString()] if as_list else _BadString()
    with pytest.raises(ValueError, match="cannot convert file id"):
        getattr(selection_api, operation)(value)


@pytest.mark.parametrize(
    "operation", ["normalize_selected_file_ids", "merge_unique_file_ids"]
)
def test_equality_errors_propagate(selection_api, operation):
    with pytest.raises(TypeError, match="file id comparison failed"):
        getattr(selection_api, operation)(_BadEquality())


def test_only_merge_uses_file_id_truthiness(selection_api):
    value = _BadTruth()
    assert selection_api.normalize_selected_file_ids(value) == ["file-value"]
    with pytest.raises(RuntimeError, match="file id truth check failed"):
        selection_api.merge_unique_file_ids(value)


@pytest.mark.parametrize("module_name", LEGACY_MODULES)
def test_legacy_function_signatures(module_name):
    module = importlib.import_module(module_name)
    assert str(inspect.signature(module.normalize_selected_file_ids)) == (
        "(selected_file_ids: 'Any') -> 'list[str]'"
    )
    assert str(inspect.signature(module.merge_unique_file_ids)) == (
        "(*groups: 'Any') -> 'list[str]'"
    )


@pytest.mark.parametrize("module_name, class_name, lookup_module", STATIC_CONSUMERS)
def test_legacy_wrappers_remain_static_methods(module_name, class_name, lookup_module):
    owner = getattr(importlib.import_module(module_name), class_name)
    for name in ("_normalize_selected_file_ids", "_merge_unique_file_ids"):
        assert isinstance(inspect.getattr_static(owner, name), staticmethod)
    instance = object.__new__(owner)
    assert instance._normalize_selected_file_ids([0, False, " a "]) == [
        "0",
        "False",
        " a ",
    ]
    assert instance._merge_unique_file_ids([0, False, " a "]) == ["a"]


@pytest.mark.parametrize("module_name, class_name, lookup_module", STATIC_CONSUMERS)
@pytest.mark.parametrize(
    "function, arguments",
    [
        ("normalize_selected_file_ids", ([" file-1 "],)),
        ("merge_unique_file_ids", (["file-1"], "file-2")),
    ],
)
def test_static_consumers_use_existing_patch_locations(
    monkeypatch, module_name, class_name, lookup_module, function, arguments
):
    owner = getattr(importlib.import_module(module_name), class_name)
    lookup = importlib.import_module(lookup_module)
    result = ["patched-result"]
    calls = []

    def replacement(*args):
        calls.append(args)
        return result

    monkeypatch.setattr(lookup, function, replacement)
    assert getattr(owner, "_" + function)(*arguments) is result
    assert calls == [arguments]


@pytest.mark.parametrize("module_name", LEGACY_MODULES)
def test_selector_extraction_retains_its_local_merge_patch(monkeypatch, module_name):
    module = importlib.import_module(module_name)
    result = ["patched-result"]
    calls = []

    def replacement(*args):
        calls.append(args)
        return result

    monkeypatch.setattr(module, "merge_unique_file_ids", replacement)
    assert (
        module.extract_selected_ids_from_data_source(
            {"selected": {"source": ["file-1", "file-2"]}}
        )
        is result
    )
    assert calls == [(["file-1", "file-2"],)]


def test_graph_runtime_composes_existing_chat_helpers():
    from ktem.pages.chat import ChatPage, chat_knowledge_graph_runtime

    assert chat_knowledge_graph_runtime._source_scope(
        ChatPage, [" graph ", "dup"], [" selected ", "dup", 0, False], " focus "
    ) == ["graph", "dup", "selected", "0", "False", "focus"]


def test_docqa_artifact_scope_uses_existing_merge_semantics():
    from ktem.docqa._runtime_models import DocQARequest, _PreparedPipeline
    from ktem.docqa.runtime import _artifact_source_scope

    request = DocQARequest(
        prompt="fixed request", qa_scope="document", note_ids=[" n ", "n", "n2", ""]
    )
    prepared = _PreparedPipeline(
        pipeline=None,
        reasoning_state={},
        selected_file_ids=[" f1 ", "f2", "f1"],
        active_file_id=" f3 ",
        active_file_name="",
        qa_scope="multi_document",
        page_number=2,
        selected_text="",
        graph_context={},
        settings={},
        reasoning_id="fixed-reasoning",
    )
    assert _artifact_source_scope(request, prepared, [" g ", "f2"]) == {
        "mode": "multi_document",
        "source_ids": ["g", "f2", "f1", "f3"],
        "page": 2,
        "note_ids": ["n", "n2"],
    }
