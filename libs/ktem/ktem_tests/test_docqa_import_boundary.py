"""New cold-import goals, separate from the pre-refactor public contract."""

from __future__ import annotations

import pytest
from ktem_tests.docqa_import_test_helpers import run_docqa_import_probe

HEAVY_PREFIXES = (
    "ktem.docqa.runtime",
    "ktem.docqa.execution",
    "ktem.docqa.controller",
    "ktem.db",
    "ktem.index",
    "ktem.llms",
    "ktem.embeddings",
    "ktem.rerankings",
    "gradio",
    "sqlmodel",
    "llama_index",
    "torch",
)


@pytest.mark.parametrize(
    "source, expected_docqa_modules",
    [
        ("import ktem.docqa", {"ktem.docqa"}),
        (
            "import ktem.docqa as docqa\nbefore = set(sys.modules)\n"
            "assert set(docqa.__all__) <= set(dir(docqa))\n"
            "assert set(sys.modules) == before\n",
            {"ktem.docqa"},
        ),
        (
            "from ktem.docqa import (DocQARequest, DocQAResponse, DocQATurnUpdate, "
            "DocQASession, DocQASessionSummary, DocQAFileRecord, DocQAIndexResult, "
            "DocQADoctorResult)\n"
            "assert DocQARequest('Question').prompt == 'Question'\n"
            "assert DocQATurnUpdate().is_final is False\n",
            {"ktem.docqa", "ktem.docqa._runtime_models", "ktem.docqa._runtime_utils"},
        ),
    ],
    ids=("package", "discovery", "eight-data-types"),
)
def test_light_access_adds_no_execution_stack_or_runtime_side_effects(
    source, expected_docqa_modules
):
    result = run_docqa_import_probe(source)
    unexpected = [
        name
        for name in result["added_modules"]
        if any(
            name == prefix or name.startswith(prefix + ".") for prefix in HEAVY_PREFIXES
        )
    ]
    assert unexpected == []
    assert {
        name for name in result["added_modules"] if name.startswith("ktem.docqa")
    } == expected_docqa_modules
    assert result["added_events"] == []


def test_unknown_attribute_does_not_import_or_cache_anything():
    result = run_docqa_import_probe(
        """
import ktem.docqa as docqa
before = set(sys.modules)
try:
    docqa.not_a_docqa_export
except AttributeError as error:
    assert 'not_a_docqa_export' in str(error)
else:
    raise AssertionError('Unknown attribute was accepted')
assert 'not_a_docqa_export' not in vars(docqa)
assert set(sys.modules) == before
"""
    )
    assert result["added_modules"] == ["ktem.docqa"]


def test_successful_attribute_access_caches_the_original_object_once():
    run_docqa_import_probe(
        """
original_import = importlib.import_module
calls = []
def counted_import(name, package=None):
    calls.append((name, package))
    return original_import(name, package)
importlib.import_module = counted_import
import ktem.docqa as docqa
first = docqa.DocQARequest
after_first = list(calls)
assert first is vars(docqa)['DocQARequest']
assert len(after_first) == 1
for _ in range(3):
    assert docqa.DocQARequest is first
assert calls == after_first
assert 'ktem.docqa.runtime' not in sys.modules
"""
    )


@pytest.mark.parametrize(
    "error_type", ["ImportError", "ModuleNotFoundError", "RuntimeError"]
)
def test_real_module_loading_errors_propagate_without_caching_partial_results(
    error_type,
):
    run_docqa_import_probe(
        """
import importlib.abc
import importlib.util
import ktem.docqa as docqa
assert 'ktem.docqa.runtime' not in sys.modules
"""
        + f"failure = {error_type}('runtime initialization sentinel')\n"
        + """
class FailingLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        raise failure

class FailRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'ktem.docqa.runtime':
            return importlib.util.spec_from_loader(fullname, FailingLoader())

finder = FailRuntime()
sys.meta_path.insert(0, finder)
for _ in range(2):
    try:
        docqa.DocQARuntime
    except Exception as error:
        assert error is failure
    else:
        raise AssertionError('Module loading failure was swallowed')
    assert 'DocQARuntime' not in vars(docqa)
    assert 'ktem.docqa.runtime' not in sys.modules
sys.meta_path.remove(finder)
from ktem.docqa.runtime import DocQARuntime
assert docqa.DocQARuntime is DocQARuntime
"""
    )
