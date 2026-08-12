from types import SimpleNamespace

import pytest


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _stmt):
        return self._rows


def _build_manager(module, manager_cls):
    manager = manager_cls.__new__(manager_cls)
    manager._models = {}
    manager._info = {}
    manager._default = ""
    manager._vendors = []
    manager._load_errors = []
    return manager


def _exercise_manager_lazy_load(
    monkeypatch, module, manager_cls, *, expect_default_alias
):
    broken = SimpleNamespace(name="broken", spec={"__type__": "broken"}, default=True)
    working = SimpleNamespace(
        name="working", spec={"__type__": "working"}, default=False
    )
    rows = [(broken,), (working,)]
    deserialize_calls: list[str] = []

    monkeypatch.setattr(module, "Session", lambda _engine: _FakeSession(rows))

    def _fake_deserialize(spec, safe=False):
        deserialize_calls.append(spec["__type__"])
        if spec["__type__"] == "broken":
            raise ValueError("missing credential")
        return {"loaded": spec["__type__"]}

    monkeypatch.setattr(module, "deserialize", _fake_deserialize)

    manager = _build_manager(module, manager_cls)
    manager.load()

    assert deserialize_calls == []
    assert manager._models == {}
    assert manager._default == "broken"
    assert manager.load_errors() == []
    assert set(manager.info().keys()) == {"broken", "working"}
    assert "load_error" not in manager.info()["broken"]
    assert set(manager.options().keys()) == (
        {"broken", "working", "default"}
        if expect_default_alias
        else {"broken", "working"}
    )
    assert manager.get_default_name() == "broken"
    settings = manager.settings()
    assert settings["choices"] == ["broken", "working"]
    assert settings["value"] == "broken"
    assert "working" in manager
    assert "broken" in manager

    assert manager.get("working") == {"loaded": "working"}
    assert deserialize_calls == ["working"]
    assert manager.load_errors() == []

    with pytest.raises(ValueError, match="missing credential"):
        manager.get_default()

    assert deserialize_calls == ["working", "broken"]
    assert manager.info()["broken"]["load_error"] == "missing credential"
    assert manager.load_errors() == ["broken: missing credential"]
    assert manager.get("missing") is None
    assert manager.get("missing", "fallback") == "fallback"

    with pytest.raises(ValueError, match="missing credential"):
        manager["broken"]

    assert deserialize_calls == ["working", "broken", "broken"]


def test_embedding_manager_deserializes_on_access(monkeypatch):
    import ktem.embeddings.manager as module

    _exercise_manager_lazy_load(
        monkeypatch,
        module,
        module.EmbeddingManager,
        expect_default_alias=True,
    )


def test_llm_manager_deserializes_on_access(monkeypatch):
    import ktem.llms.manager as module

    _exercise_manager_lazy_load(
        monkeypatch,
        module,
        module.LLMManager,
        expect_default_alias=False,
    )


def test_reranking_manager_deserializes_on_access(monkeypatch):
    import ktem.rerankings.manager as module

    _exercise_manager_lazy_load(
        monkeypatch,
        module,
        module.RerankingManager,
        expect_default_alias=False,
    )


def test_reranking_manager_lists_local_multilingual_vendor():
    import ktem.rerankings.manager as module

    manager = _build_manager(module, module.RerankingManager)

    assert "LocalMultilingualReranking" in manager.vendors()


@pytest.mark.parametrize(
    ("module_name", "manager_name"),
    [
        ("ktem.llms.manager", "LLMManager"),
        ("ktem.embeddings.manager", "EmbeddingManager"),
    ],
)
def test_desktop_manager_hydrates_runtime_secret_without_using_persisted_spec(
    monkeypatch,
    module_name,
    manager_name,
):
    module = __import__(module_name, fromlist=[manager_name])
    manager = _build_manager(module, getattr(module, manager_name))
    manager._desktop = True
    manager._info = {
        "openai": {
            "name": "openai",
            "spec": {
                "__type__": "provider.Type",
                "model": "gpt-5.6-luna",
                "secret_ref": "desktop-safe-storage:chat",
            },
            "default": True,
        }
    }
    manager._default = "openai"
    manager._runtime_specs = {
        "openai": {
            "__type__": "provider.Type",
            "model": "gpt-5.6-luna",
            "api_key": "runtime-only-secret",
        }
    }
    received: list[dict] = []

    def deserialize(spec, safe=False):
        received.append(dict(spec))
        return {"model": spec["model"]}

    monkeypatch.setattr(module, "deserialize", deserialize)

    assert manager.get_default() == {"model": "gpt-5.6-luna"}
    assert received == [manager._runtime_specs["openai"]]
    assert "api_key" not in manager.info()["openai"]["spec"]


@pytest.mark.parametrize(
    ("module_name", "manager_name"),
    [
        ("ktem.llms.manager", "LLMManager"),
        ("ktem.embeddings.manager", "EmbeddingManager"),
    ],
)
def test_desktop_manager_never_randomly_selects_a_stale_nondefault_route(
    module_name,
    manager_name,
):
    module = __import__(module_name, fromlist=[manager_name])
    manager = _build_manager(module, getattr(module, manager_name))
    manager._desktop = True
    manager._info = {
        "legacy": {
            "name": "legacy",
            "spec": {"__type__": "legacy.Type"},
            "default": False,
        }
    }

    with pytest.raises(ValueError, match="No default Desktop"):
        manager.get_default_name()
