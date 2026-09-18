"""Fixed external-store expectations recorded before the R5-A extraction."""

from types import SimpleNamespace
from typing import Any

import pytest
from ktem.index.file import deletion
from ktem.index.file.deletion import DeletionCoordinator, DeletionError


def coordinator():
    return DeletionCoordinator(
        engine=None,
        source_table=None,
        index_table=None,
        vector_store=None,
        doc_store=None,
        file_storage_path=None,
    )


@pytest.mark.parametrize("stage", ["vector", "docstore"])
@pytest.mark.parametrize("ids,store", [((), object()), (("a",), None)])
def test_empty_ids_or_absent_store_never_calls_a_patch(stage, ids, store, monkeypatch):
    subject = coordinator()
    for method in ("_delete_store_batch", "_refresh_docstore_index"):
        monkeypatch.setattr(subject, method, lambda *_a: pytest.fail("not reached"))
    assert subject._delete_store(stage, store, ids, "file") is None


@pytest.mark.parametrize("stage", ["vector", "docstore", "custom-stage"])
def test_batch_keeps_order_duplicates_and_copies_ids(stage):
    calls = []
    ids = ("z", "a", "z", "")

    def delete(values, **kwargs):
        calls.append((values.copy(), kwargs))
        values.clear()

    def refresh(*args, **kwargs):
        calls.append((args, kwargs))

    store = SimpleNamespace(delete=delete, create_fts_index=refresh)
    coordinator()._delete_store(stage, store, ids, "file")
    expected: list[Any] = [
        (list(ids), {"refresh_indices": False} if stage == "docstore" else {})
    ]
    if stage == "docstore":
        expected.append((("text",), {"tokenizer_name": "en_stem", "replace": True}))
    assert calls == expected
    assert ids == ("z", "a", "z", "")


def status_error(status=None, code=None):
    error: Any = RuntimeError("external response")
    error.status_code = status
    error.code = code
    return error


@pytest.mark.parametrize(
    "missing",
    [
        FileNotFoundError("gone"),
        KeyError("gone"),
        status_error(404),
        status_error(code="404"),
        status_error(code=" NOT_FOUND "),
        status_error(code="not-found"),
    ],
)
@pytest.mark.parametrize("stage", ["vector", "docstore"])
def test_only_explicit_missing_replays_every_id_and_refreshes_last(missing, stage):
    calls = []

    def delete(values, **kwargs):
        calls.append((values.copy(), kwargs))
        if len(values) > 1 or values == ["missing"]:
            raise missing

    store = SimpleNamespace(
        delete=delete,
        create_fts_index=lambda *a, **kw: calls.append((a, kw)),
    )
    coordinator()._delete_store(stage, store, ("b", "missing", "a", "b"), "file")
    kwargs = {"refresh_indices": False} if stage == "docstore" else {}
    assert calls[:5] == [
        (ids, kwargs)
        for ids in (["b", "missing", "a", "b"], ["b"], ["missing"], ["a"], ["b"])
    ]
    assert calls[5:] == (
        [(("text",), {"tokenizer_name": "en_stem", "replace": True})]
        if stage == "docstore"
        else []
    )


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("not found"),
        ValueError("missing"),
        status_error("404"),
        status_error(500),
        status_error(code="NotFound"),
        TypeError("invalid backend"),
    ],
)
@pytest.mark.parametrize("stage", ["vector", "docstore"])
def test_nonmissing_batch_failure_has_one_call_and_original_cause(error, stage):
    calls = []

    def delete(values, **kwargs):
        calls.append(values.copy())
        raise error

    store = SimpleNamespace(
        delete=delete, create_fts_index=lambda *_a, **_k: pytest.fail()
    )
    with pytest.raises(DeletionError) as raised:
        coordinator()._delete_store(stage, store, ("a", "b"), "file")
    assert (raised.value.stage, raised.value.file_id) == (stage, "file")
    assert raised.value.__cause__ is error
    assert raised.value.reason == f"{type(error).__name__}: {error}"
    assert calls == [["a", "b"]]


@pytest.mark.parametrize("stage", ["vector", "docstore"])
def test_individual_nonmissing_failure_stops_before_later_ids_and_fts(stage):
    calls = []
    error = OSError("write unavailable")

    def delete(ids, **_kwargs):
        calls.append(ids.copy())
        if len(ids) > 1 or ids == ["gone"]:
            raise KeyError("gone")
        if ids == ["bad"]:
            raise error

    store = SimpleNamespace(
        delete=delete, create_fts_index=lambda *_a, **_kw: pytest.fail()
    )
    with pytest.raises(DeletionError) as raised:
        coordinator()._delete_store(stage, store, ("gone", "bad", "later"), "file")
    assert calls == [["gone", "bad", "later"], ["gone"], ["bad"]]
    assert raised.value.stage == stage
    assert raised.value.__cause__ is error


def test_old_docstore_signature_fallback_copies_again_and_does_not_retry_twice():
    calls = []
    error = TypeError("legacy backend failed")

    def delete(ids, **kwargs):
        calls.append((ids.copy(), kwargs))
        ids.clear()
        if kwargs:
            raise TypeError("unexpected refresh_indices")
        raise error

    with pytest.raises(TypeError) as raised:
        coordinator()._delete_docstore_entries(
            SimpleNamespace(delete=delete), ("b", "a")
        )
    assert raised.value is error
    assert calls == [(["b", "a"], {"refresh_indices": False}), (["b", "a"], {})]


def test_legacy_signature_and_missing_replay_keep_original_call_order():
    calls = []

    class Legacy:
        def delete(self, ids):
            calls.append(ids)
            if len(ids) > 1:
                raise KeyError("missing")

    coordinator()._delete_store("docstore", Legacy(), ("z", "a"), "file")
    assert calls == [["z", "a"], ["z"], ["a"]]


@pytest.mark.parametrize(
    "error", [RuntimeError("refresh_indices"), TypeError("Refresh_Indices")]
)
def test_docstore_compatibility_is_limited_to_literal_typeerror(error):
    calls = []

    def delete(ids, **kwargs):
        calls.append((ids, kwargs))
        raise error

    with pytest.raises(type(error)) as raised:
        coordinator()._delete_docstore_entries(SimpleNamespace(delete=delete), ("id",))
    assert raised.value is error
    assert calls == [(["id"], {"refresh_indices": False})]


def test_fts_failure_is_docstore_failure_after_one_completed_delete():
    calls = []
    error = KeyError("missing FTS")

    def refresh(*args, **kwargs):
        calls.append((args, kwargs))
        raise error

    store = SimpleNamespace(
        delete=lambda ids, **kwargs: calls.append((ids, kwargs)),
        create_fts_index=refresh,
    )
    with pytest.raises(DeletionError) as raised:
        coordinator()._delete_store("docstore", store, ("id",), "file")
    assert calls == [
        (["id"], {"refresh_indices": False}),
        (("text",), {"tokenizer_name": "en_stem", "replace": True}),
    ]
    assert raised.value.stage == "docstore" and raised.value.__cause__ is error


def test_fts_lookup_error_is_not_wrapped_or_retried():
    error = RuntimeError("descriptor failure")

    class Store:
        @property
        def create_fts_index(self):
            raise error

    with pytest.raises(RuntimeError) as raised:
        coordinator()._refresh_docstore_index(Store(), "file")
    assert raised.value is error


def test_compatibility_methods_and_error_patches_remain_consumed(monkeypatch):
    subject = coordinator()
    calls = []
    ids = ("a", "b")
    store = object()
    marker = RuntimeError("missing patch")

    def batch(*args):
        calls.append(("batch", args))
        raise marker

    monkeypatch.setattr(subject, "_delete_store_batch", batch)
    monkeypatch.setattr(deletion, "_is_missing_error", lambda error: error is marker)
    monkeypatch.setattr(
        subject, "_delete_store_individually", lambda *a: calls.append(("each", a))
    )
    monkeypatch.setattr(
        subject, "_refresh_docstore_index", lambda *a: calls.append(("fts", a))
    )
    subject._delete_store("docstore", store, ids, "file")
    assert calls == [
        ("batch", ("docstore", store, ids)),
        ("each", ("docstore", store, ids, "file")),
        ("fts", (store, "file")),
    ]

    entries = []
    monkeypatch.setattr(
        subject, "_delete_docstore_entries", lambda *a: entries.append(a)
    )
    DeletionCoordinator._delete_store_batch(subject, "docstore", store, ids)
    DeletionCoordinator._delete_store_individually(
        subject, "docstore", store, ids, "file"
    )
    assert entries == [(store, ids), (store, ("a",)), (store, ("b",))]


def test_error_factory_patch_is_used_for_individual_and_fts_failures(monkeypatch):
    subject = coordinator()
    original = OSError("backend")
    replacement = RuntimeError("patched failure")
    calls = []

    def fail(*_args, **_kwargs):
        raise original

    def factory(*args):
        calls.append(args)
        return replacement

    monkeypatch.setattr(deletion, "_stage_error", factory)
    store = SimpleNamespace(delete=fail, create_fts_index=fail)
    for call in (
        lambda: subject._delete_store_individually("vector", store, ("a",), "file"),
        lambda: subject._refresh_docstore_index(store, "file"),
    ):
        with pytest.raises(RuntimeError) as raised:
            call()
        assert raised.value is replacement and raised.value.__cause__ is original
    assert calls == [("vector", "file", original), ("docstore", "file", original)]
