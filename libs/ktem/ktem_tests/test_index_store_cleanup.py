"""The leaf mechanics need only store operations, not a coordinator or database."""

from types import SimpleNamespace
from typing import Any

import pytest
from ktem.index.file import index_store_cleanup as cleanup

from .docqa_import_test_helpers import run_docqa_import_probe


def test_independent_cleanup_calls_and_error_factory():
    calls: list[Any] = []
    error = OSError("backend failure")

    def delete(ids, **kwargs):
        calls.append((ids, kwargs))
        if ids == ["missing"]:
            raise KeyError("missing")
        if ids == ["bad"]:
            raise error

    def stage_error(stage, file_id, cause):
        calls.append((stage, file_id, cause))
        return RuntimeError("owned stage error")

    store = SimpleNamespace(delete=delete)
    cleanup.delete_store_batch(
        "docstore",
        store,
        ("z", "a", "z"),
        delete_docstore=cleanup.delete_docstore_entries,
    )
    with pytest.raises(RuntimeError, match="owned stage error") as raised:
        cleanup.delete_store_individually(
            "docstore",
            store,
            ("missing", "ok", "bad", "later"),
            "file",
            delete_docstore=cleanup.delete_docstore_entries,
            is_missing_error=lambda exc: isinstance(exc, KeyError),
            stage_error=stage_error,
        )
    assert raised.value.__cause__ is error
    assert calls == [
        (["z", "a", "z"], {"refresh_indices": False}),
        (["missing"], {"refresh_indices": False}),
        (["ok"], {"refresh_indices": False}),
        (["bad"], {"refresh_indices": False}),
        ("docstore", "file", error),
    ]


def test_real_parent_cold_import_adds_no_reverse_dependency_or_io():
    result = run_docqa_import_probe(
        """
import ktem.index.file
parent_modules = set(sys.modules)
parent_events = list(events)
assert 'ktem.index.file.index_store_cleanup' not in sys.modules
import ktem.index.file.index_store_cleanup
assert 'ktem.index.file.deletion' not in sys.modules
"""
    )
    assert result["added_modules"] == ["ktem.index.file.index_store_cleanup"]
    assert result["added_events"] == []
