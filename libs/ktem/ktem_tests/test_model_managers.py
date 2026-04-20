from types import SimpleNamespace


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _stmt):
        return self._rows


def _exercise_manager_load(monkeypatch, module, manager_cls):
    broken = SimpleNamespace(name="broken", spec={"__type__": "broken"}, default=True)
    working = SimpleNamespace(name="working", spec={"__type__": "working"}, default=False)
    rows = [(broken,), (working,)]

    monkeypatch.setattr(module, "Session", lambda _engine: _FakeSession(rows))
    monkeypatch.setattr(
        module,
        "deserialize",
        lambda spec, safe=False: (_ for _ in ()).throw(ValueError("missing credential"))
        if spec["__type__"] == "broken"
        else {"loaded": spec["__type__"]},
    )

    manager = manager_cls.__new__(manager_cls)
    manager._models = {}
    manager._info = {}
    manager._default = ""
    manager._vendors = []
    manager._load_errors = []
    manager.load()

    assert manager._models == {"working": {"loaded": "working"}}
    assert manager._default == ""
    assert manager._info["broken"]["load_error"] == "missing credential"
    assert manager.load_errors() == ["broken: missing credential"]


def test_embedding_manager_skips_invalid_specs(monkeypatch):
    import ktem.embeddings.manager as module

    _exercise_manager_load(monkeypatch, module, module.EmbeddingManager)


def test_llm_manager_skips_invalid_specs(monkeypatch):
    import ktem.llms.manager as module

    _exercise_manager_load(monkeypatch, module, module.LLMManager)


def test_reranking_manager_skips_invalid_specs(monkeypatch):
    import ktem.rerankings.manager as module

    _exercise_manager_load(monkeypatch, module, module.RerankingManager)
