"""Real-file contracts shared by the existing Runtime and Web cache seams."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa import knowledge_graph as runtime_graph
from ktem.docqa import knowledge_graph_cache as cache_io
from ktem.pages.chat import knowledge_graph_service as web_graph


@pytest.fixture(params=[runtime_graph, web_graph], ids=["runtime", "web"])
def cache(request, monkeypatch, tmp_path):
    module = request.param
    monkeypatch.setattr(module.flowsettings, "KH_APP_DATA_DIR", tmp_path)
    service = module.GlobalKnowledgeGraphService(SimpleNamespace(), None)
    return service, module


def test_cache_characterization_missing_and_normal_round_trip(cache):
    service, module = cache
    empty: dict[str, Any] = {"conversation_id": "conv-1", "manifest": {}, "graph": None}
    if module is web_graph:
        empty["schema_version"] = 0
    assert service._load_cached_state("conv-1") == empty
    state = dict(empty, manifest={"a": "sig-a", "b": "sig-b"})
    state["graph"] = {"nodes": [{"id": "b"}, {"id": "a", "label": "中文"}]}
    service._save_cached_state("conv-1", state)
    assert service._get_storage_path("conv-1").read_text("utf-8") == json.dumps(
        state, ensure_ascii=False, indent=2
    )
    assert service._load_cached_state("conv-1") == state
    state["graph"]["nodes"].clear()
    assert len(service._load_cached_state("conv-1")["graph"]["nodes"]) == 2


def test_cache_characterization_legacy_defaults_and_corrupt_json(cache):
    service, module = cache
    path = service._get_storage_path("conv-1")
    path.write_text('{"legacy": "kept"}', encoding="utf-8")
    loaded = service._load_cached_state("conv-1")
    assert loaded["legacy"] == "kept"
    assert loaded["manifest"] == {} and loaded["graph"] is None
    path.write_text('{"graph":', encoding="utf-8")
    assert service._load_cached_state("conv-1")["graph"] is None
    assert path.read_text("utf-8") == '{"graph":'


def test_failed_encoding_preserves_completed_snapshot(cache):
    service, module = cache
    state = {"conversation_id": "conv-1", "manifest": {}, "graph": {"old": True}}
    service._save_cached_state("conv-1", state)
    path = service._get_storage_path("conv-1")
    before = path.read_bytes()
    with pytest.raises(TypeError):
        service._save_cached_state("conv-1", {"graph": {"bad": object()}})
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


def test_reader_cannot_observe_half_written_snapshot(cache, monkeypatch):
    service, module = cache
    old = {"conversation_id": "conv-1", "manifest": {}, "graph": {"old": True}}
    service._save_cached_state("conv-1", old)
    path = service._get_storage_path("conv-1")
    before = path.read_bytes()
    dump = module.json.dump
    observed = []

    def partial_dump(state, handle, **kwargs):
        handle.write('{"graph":')
        handle.flush()
        observed.append(path.read_bytes())
        raise OSError("controlled partial write")

    monkeypatch.setattr(module.json, "dump", partial_dump)
    with pytest.raises(OSError, match="controlled partial write"):
        service._save_cached_state("conv-1", {"graph": {"new": True}})
    monkeypatch.setattr(module.json, "dump", dump)
    assert observed == [before]
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("raw", ["[]", "null", "42", '"text"'])
def test_wrong_top_level_cache_is_diagnosed_as_unusable(cache, raw, caplog):
    service, module = cache
    path = service._get_storage_path("conv-1")
    path.write_text(raw, encoding="utf-8")
    assert service._load_cached_state("conv-1")["graph"] is None
    assert "cache" in caplog.text.lower()
    assert path.read_text("utf-8") == raw


def test_cache_permission_failure_is_not_reported_as_a_cache_miss(cache, monkeypatch):
    service, _module = cache
    path = service._get_storage_path("conv-1")
    path.write_text("{}", encoding="utf-8")
    original = type(path).open

    def forbidden(current, *args, **kwargs):
        if current == path:
            raise PermissionError("owned cache permission failure")
        return original(current, *args, **kwargs)

    monkeypatch.setattr(type(path), "open", forbidden)
    with pytest.raises(PermissionError, match="owned cache permission"):
        service._load_cached_state("conv-1")


@pytest.mark.parametrize("stage", ["allocate", "flush", "fsync", "close", "replace"])
def test_publication_failures_keep_old_bytes_and_release_owned_temp(
    cache, monkeypatch, stage
):
    service, _ = cache
    service._save_cached_state("conv-1", {"graph": {"old": True}})
    path = service._get_storage_path("conv-1")
    before = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError(stage)

    if stage in {"fsync", "replace"}:
        monkeypatch.setattr(cache_io.os, stage, fail)
    elif stage == "allocate":
        monkeypatch.setattr(cache_io.tempfile, "NamedTemporaryFile", fail)
    else:
        allocate = cache_io.tempfile.NamedTemporaryFile

        def instrument(*args, **kwargs):
            stream = allocate(*args, **kwargs)
            operation = getattr(stream, stage)
            called = False

            def fail_once():
                nonlocal called
                operation()
                if not called:
                    called = True
                    fail()

            setattr(stream, stage, fail_once)
            return stream

        monkeypatch.setattr(cache_io.tempfile, "NamedTemporaryFile", instrument)
    with pytest.raises(OSError, match=stage):
        service._save_cached_state("conv-1", {"graph": {"new": True}})
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


def test_post_replace_failure_is_published_and_never_rolled_back(cache, monkeypatch):
    service, _ = cache
    replace = cache_io.os.replace

    def replace_then_fail(*args):
        replace(*args)
        raise OSError("after publication")

    monkeypatch.setattr(cache_io.os, "replace", replace_then_fail)
    with pytest.raises(OSError, match="after publication"):
        service._save_cached_state("conv-1", {"graph": {"new": True}})
    assert service._load_cached_state("conv-1")["graph"] == {"new": True}


def test_cleanup_failure_retains_primary_error_and_reports_residue(
    cache, monkeypatch, caplog
):
    service, _ = cache
    path = service._get_storage_path("conv-1")
    unlink = type(path).unlink

    def deny_cleanup(self, **kwargs):
        if self.suffix == ".tmp":
            raise OSError("cleanup denied")
        return unlink(self, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(type(path), "unlink", deny_cleanup)
        with pytest.raises(TypeError):
            service._save_cached_state("conv-1", {"graph": object()})
    assert "cleanup denied" in caplog.text
    assert not path.exists()
    residues = list(path.parent.iterdir())
    assert len(residues) == 1 and residues[0].suffix == ".tmp"
    residues[0].unlink()
