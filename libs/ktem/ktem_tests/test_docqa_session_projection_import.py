"""Cold projection calls must stay within the real parent's light dependencies."""

from __future__ import annotations

from ktem_tests.docqa_import_test_helpers import run_docqa_import_probe


def test_session_projection_import_and_calls_add_no_runtime_or_side_effects():
    result = run_docqa_import_probe(
        """
from datetime import datetime
from types import SimpleNamespace

from ktem.docqa import session_projection
from ktem.docqa._runtime_models import DocQASession, DocQASessionSummary

assert Path(session_projection.__file__).parent == Path(ktem.__file__).parent / 'docqa'
created = datetime(2026, 9, 1)
state = {'app': {'regen': False}, 'extra': {'values': [1]}}
row = SimpleNamespace(id='cold-session', name='Cold record', user='owner',
    is_public=False, date_created=created, date_updated=None,
    data_source={'messages': [['q', 'a'], ['q2', 'a2']],
                 'retrieval_messages': ['refs'],
                 'selected': {'9': ['select', ['file-2', 'file-1'], 'owner']}})
summary = session_projection.session_summary(row)
loaded = session_projection.loaded_session(row, default_state=state)
assert type(summary) is DocQASessionSummary
assert type(loaded) is DocQASession
assert loaded.__class__.__module__ == 'ktem.docqa._runtime_models'
assert summary.message_count == 2 and summary.graph_source_count == 0
assert loaded.messages == [('q', 'a'), ('q2', 'a2')]
assert loaded.retrieval_messages == ['refs', '']
assert loaded.graph_source_ids == ['file-2', 'file-1']
assert loaded.date_created is created
loaded.state['extra']['values'].append(2)
assert state['extra']['values'] == [1]
row.data_source = None
assert session_projection.session_summary(row).message_count == 0
assert session_projection.loaded_session(row, default_state=state).messages == []
"""
    )
    blocked = (
        "ktem.docqa.runtime",
        "ktem.docqa._runtime_session_service",
        "ktem.docqa._runtime_sessions",
        "ktem.docqa._runtime_notebook",
        "ktem.docqa.execution",
        "ktem.docqa.controller",
        "ktem.db",
        "ktem.index",
        "ktem.llms",
        "ktem.embeddings",
        "ktem.rerankings",
        "gradio",
        "sqlmodel",
        "sqlalchemy",
        "llama_index",
        "torch",
    )
    assert not any(
        name == prefix or name.startswith(prefix + ".")
        for name in result["added_modules"]
        for prefix in blocked
    ), result["added_modules"]
    assert {
        name for name in result["added_modules"] if name.startswith("ktem.docqa")
    } == {
        "ktem.docqa",
        "ktem.docqa.session_projection",
        "ktem.docqa._runtime_models",
        "ktem.docqa._runtime_utils",
        "ktem.docqa._runtime_selection",
    }
    assert result["added_events"] == []
