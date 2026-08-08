import sys
from types import ModuleType, SimpleNamespace

import pytest
from slide_cli import docqa_import_capabilities as import_capabilities
from slide_cli.docqa_import_capabilities import (
    collect_docqa_import_capabilities,
    normalize_supported_extensions,
    select_file_index_config,
)


def test_persisted_file_index_config_wins_over_the_default_definition():
    settings = SimpleNamespace(
        KH_INDICES=[
            {
                "index_type": "ktem.index.file.FileIndex",
                "config": {"supported_file_types": ".txt, .md"},
            }
        ]
    )
    rows = [
        SimpleNamespace(
            index_type="ktem.index.file.FileIndex",
            config={"supported_file_types": ".pdf, .docx"},
        )
    ]

    assert select_file_index_config(settings, rows) == {
        "supported_file_types": ".pdf, .docx"
    }
    assert select_file_index_config(settings, []) == {
        "supported_file_types": ".txt, .md"
    }
    assert select_file_index_config(SimpleNamespace(KH_INDICES=[]), []) == {}


def test_supported_extensions_are_stable_deduplicated_and_safe():
    assert normalize_supported_extensions(
        ".PDF, .md, .pdf, ../secret, *, .tar.gz, .csv"
    ) == [".pdf", ".md", ".csv"]


def test_collects_capabilities_from_the_persisted_file_index(monkeypatch):
    bootstrap_calls = _install_runtime_modules(
        monkeypatch,
        rows=[
            SimpleNamespace(
                index_type="ktem.index.file.FileIndex",
                config={"supported_file_types": ".PDF, .md, .pdf"},
            )
        ],
        definitions=[],
    )

    assert collect_docqa_import_capabilities() == {
        "supported_extensions": [".pdf", ".md"]
    }
    assert bootstrap_calls == ["bootstrap"]


def test_collect_capabilities_rejects_an_empty_configuration(monkeypatch):
    _install_runtime_modules(monkeypatch, rows=[], definitions=[])

    with pytest.raises(RuntimeError, match="No supported DocQA file types"):
        collect_docqa_import_capabilities()


def test_runtime_facade_delegates_to_the_capability_service(monkeypatch):
    from slide_cli import docqa_runtime

    expected = {"supported_extensions": [".txt"]}
    monkeypatch.setattr(
        import_capabilities,
        "collect_docqa_import_capabilities",
        lambda: expected,
    )

    assert docqa_runtime.collect_docqa_import_capabilities() == expected


def _install_runtime_modules(monkeypatch, *, rows, definitions):
    bootstrap_calls = []
    runtime_bootstrap = ModuleType("ktem.runtime_bootstrap")

    def bootstrap_runtime_settings():
        bootstrap_calls.append("bootstrap")

    setattr(runtime_bootstrap, "bootstrap_runtime_settings", bootstrap_runtime_settings)
    database_models = ModuleType("ktem.db.models")
    setattr(database_models, "engine", object())
    index_models = ModuleType("ktem.index.models")
    setattr(index_models, "Index", object())

    class FakeSession:
        def __init__(self, engine):
            assert engine is getattr(database_models, "engine")

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def exec(self, statement):
            assert statement == ("select", getattr(index_models, "Index"))
            return SimpleNamespace(all=lambda: rows)

    sqlmodel = ModuleType("sqlmodel")
    setattr(sqlmodel, "Session", FakeSession)
    setattr(sqlmodel, "select", lambda model: ("select", model))
    flow_settings = ModuleType("theflow.settings")
    setattr(flow_settings, "settings", SimpleNamespace(KH_INDICES=definitions))

    for name, module in (
        ("ktem.runtime_bootstrap", runtime_bootstrap),
        ("ktem.db.models", database_models),
        ("ktem.index.models", index_models),
        ("sqlmodel", sqlmodel),
        ("theflow.settings", flow_settings),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    return bootstrap_calls
