"""Graph/renderer unit fixture; real scopes have separate SQLite tests."""

from contextlib import nullcontext
from types import SimpleNamespace

from ktem.pages.chat.knowledge_graph_service import GlobalKnowledgeGraphService


class _DummyApp:
    pass


class _DummyIndex:
    pass


def make_service(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "ktem.pages.chat.knowledge_graph_service.flowsettings.KH_APP_DATA_DIR",
        tmp_path,
        raising=False,
    )
    # These are pure graph/renderer tests with no database or Source model.
    # Real cache scope/lease behavior is covered by test_graph_cache_interleavings.
    monkeypatch.setattr(
        "ktem.pages.chat.knowledge_graph_service.begin_graph_request",
        lambda *args, **kwargs: SimpleNamespace(
            current=nullcontext,
            draft=False,
            cache_matches=lambda state: True,
            record_publication=lambda state: None,
        ),
    )
    return GlobalKnowledgeGraphService(_DummyApp(), _DummyIndex())
