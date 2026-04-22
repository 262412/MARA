import importlib
import sys


def test_docqa_preview_modules_do_not_import_pypdf_on_import(monkeypatch):
    monkeypatch.delitem(sys.modules, "pypdf", raising=False)
    monkeypatch.delitem(sys.modules, "ktem.docqa._runtime_app", raising=False)
    monkeypatch.delitem(sys.modules, "ktem.docqa.preview_support", raising=False)

    importlib.import_module("ktem.docqa._runtime_app")
    importlib.import_module("ktem.docqa.preview_support")

    assert "pypdf" not in sys.modules


def test_model_managers_start_lazy(monkeypatch):
    monkeypatch.delitem(sys.modules, "ktem.embeddings.manager", raising=False)
    monkeypatch.delitem(sys.modules, "ktem.llms.manager", raising=False)
    monkeypatch.delitem(sys.modules, "ktem.rerankings.manager", raising=False)

    import ktem.embeddings.manager as embeddings_module
    import ktem.llms.manager as llms_module
    import ktem.rerankings.manager as rerankings_module

    assert getattr(llms_module.llms, "_manager") is None
    assert getattr(embeddings_module.embedding_models_manager, "_manager") is None
    assert getattr(rerankings_module.reranking_models_manager, "_manager") is None


def test_reasoning_simple_import_does_not_pull_umap_stack(monkeypatch):
    for module_name in [
        "ktem.reasoning.simple",
        "ktem.utils.visualize_cited",
        "umap",
        "numba",
        "pynndescent",
    ]:
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    importlib.import_module("ktem.reasoning.simple")

    assert "ktem.utils.visualize_cited" not in sys.modules
    assert "umap" not in sys.modules
    assert "numba" not in sys.modules
    assert "pynndescent" not in sys.modules


def test_react_reasoning_get_user_settings_uses_llm_manager(monkeypatch):
    import ktem.reasoning.react as react_module

    class _FakeLLMs:
        def options(self):
            return {"gpt-4o-mini": object()}

    monkeypatch.delattr(react_module, "llms", raising=False)
    monkeypatch.setattr(react_module, "_get_llms", lambda: _FakeLLMs())
    monkeypatch.setattr(react_module.mcp_manager, "get_enabled_tools", lambda: [])

    settings = react_module.ReactAgentPipeline.get_user_settings()

    assert ("gpt-4o-mini", "gpt-4o-mini") in settings["llm"]["choices"]


def test_prompt_optimization_package_defers_optional_submodules(monkeypatch):
    for module_name in [
        "ktem.reasoning.prompt_optimization",
        "ktem.reasoning.prompt_optimization.fewshot_rewrite_question",
        "ktem.reasoning.prompt_optimization.mindmap",
    ]:
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    import importlib

    package = importlib.import_module("ktem.reasoning.prompt_optimization")
    _ = package.RewriteQuestionPipeline
    _ = package.DecomposeQuestionPipeline

    assert "ktem.reasoning.prompt_optimization.fewshot_rewrite_question" not in sys.modules
    assert "ktem.reasoning.prompt_optimization.mindmap" not in sys.modules


def test_file_index_on_start_defers_storage_setup(monkeypatch):
    import ktem.index.file.index as file_index_module

    index = file_index_module.FileIndex(app=object(), id=1, name="Files", config={})
    calls: list[str] = []

    monkeypatch.setattr(
        file_index_module,
        "get_docstore",
        lambda *_args, **_kwargs: calls.append("docstore") or object(),
    )
    monkeypatch.setattr(
        file_index_module,
        "get_vectorstore",
        lambda *_args, **_kwargs: calls.append("vectorstore") or object(),
    )
    monkeypatch.setattr(
        file_index_module.FileIndex,
        "_setup_indexing_cls",
        lambda self: setattr(self, "_indexing_pipeline_cls", object()),
    )
    monkeypatch.setattr(
        file_index_module.FileIndex,
        "_setup_retriever_cls",
        lambda self: setattr(self, "_retriever_pipeline_cls", []),
    )

    index.on_start()

    assert calls == []


def test_file_index_list_source_rows_initializes_resources_on_demand(monkeypatch):
    import ktem.index.file.index as file_index_module

    index = file_index_module.FileIndex(app=object(), id=1, name="Files", config={})
    calls: list[str] = []

    class _FakeSource:
        user = "user"

    class _FakeStatement:
        def where(self, *_args, **_kwargs):
            return self

    class _FakeResult:
        def all(self):
            return []

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def exec(self, _statement):
            return _FakeResult()

    def _fake_setup_resources(self):
        calls.append("resources")
        self._resources = {"Source": _FakeSource}

    monkeypatch.setattr(file_index_module, "Session", lambda _engine: _FakeSession())
    monkeypatch.setattr(file_index_module, "select", lambda _source: _FakeStatement())
    monkeypatch.setattr(
        file_index_module.FileIndex,
        "_setup_resources",
        _fake_setup_resources,
    )

    rows = index.list_source_rows("default")

    assert rows == []
    assert calls == ["resources"]


def test_react_user_settings_uses_lazy_llm_registry(monkeypatch, caplog):
    import ktem.reasoning.react as module

    class _FakeLLMs:
        def options(self):
            return {"alpha": object(), "beta": object()}

    monkeypatch.setattr(module, "_get_llms", lambda: _FakeLLMs())
    monkeypatch.setattr(module.mcp_manager, "get_enabled_tools", lambda: [])

    with caplog.at_level("ERROR"):
        settings = module.ReactAgentPipeline.get_user_settings()

    assert settings["llm"]["choices"] == [
        ("(default)", ""),
        ("alpha", "alpha"),
        ("beta", "beta"),
    ]
    assert not any(
        "Failed to get LLM options" in record.message for record in caplog.records
    )
