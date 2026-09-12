"""Observe submission boundaries while executing their real implementations."""

from __future__ import annotations

from typing import Any

from ktem.pages.chat import chat_submission as submission
from ktem.pages.chat import chat_submit_sources as sources


class SubmissionProbe:
    def __init__(self, monkeypatch):
        self.calls = []
        self.failure = RuntimeError("submission boundary failed")
        self.fail_at = None
        self.graph_result = ["merged-graph"]
        self.choices = ObservedChoices(self, [("named.pdf", "named-id")])
        self.history = ObservedHistory(self, [["old question", "old answer"]])
        self.settings = {"reasoning.use": "mara"}
        self.context = {"nodes": [{"id": "original"}]}
        for module, name, event in (
            (submission, "resolve_chat_submit_sources", "sources"),
            (sources, "get_file_names_regex", "file_names"),
            (sources, "get_urls", "urls"),
            (sources, "_chat_uploaded_file_names", "uploaded_names"),
            (sources, "_merge_unique_file_ids", "merge_files"),
            (submission, "_inject_selected_page_text", "selection"),
            (submission.gr, "update", "update"),
        ):
            self.wrap(monkeypatch, module, name, event)

    def wrap(self, monkeypatch, module, name, event):
        original = getattr(module, name)

        def observed(*args, **kwargs):
            self.record(event, args, kwargs)
            return original(*args, **kwargs)

        monkeypatch.setattr(module, name, observed)

    def record(self, name, args=(), kwargs=None):
        self.calls.append((name, args, kwargs or {}))
        if name == self.fail_at:
            raise self.failure

    @property
    def names(self):
        return [name for name, _args, _kwargs in self.calls]

    def call(self, name):
        return next(call for call in self.calls if call[0] == name)

    def index_files(self, *args, **kwargs):
        self.record("index_files", args, kwargs)
        return ["upload-id"]

    def index_urls(self, *args, **kwargs):
        self.record("index_urls", args, kwargs)
        return ["url-id"]

    def merge_graph(self, *args):
        self.record("merge_graph", args)
        return self.graph_result

    def arguments(self, **overrides):
        values: dict[str, Any] = dict(
            chat_input={
                "text": 'Ask @"named.pdf" https://example.test/a',
                "files": ["/owned/upload.pdf"],
            },
            chat_history=self.history,
            user_id="owner",
            settings=self.settings,
            first_selector_choices=self.choices,
            graph_source_ids=["old-graph"],
            selected_page_text="  Selected\n evidence  ",
            selected_graph_context=self.context,
            default_question="Default question",
            merge_graph_source_ids=self.merge_graph,
            first_indexing_file_fn=self.index_files,
            first_indexing_url_fn=self.index_urls,
        )
        values.update(overrides)
        return values

    def prepare(self, **overrides):
        return submission.prepare_chat_submission(**self.arguments(**overrides))


class ObservedChoices(list):
    def __init__(self, probe, values):
        super().__init__(values)
        self.probe = probe

    def extend(self, values):
        self.probe.record("extend_choices", (values,))
        return super().extend(values)


class ObservedHistory(list):
    def __init__(self, probe, values):
        super().__init__(values)
        self.probe = probe

    def __add__(self, values):
        self.probe.record("append_history", (values,))
        return super().__add__(values)


FULL_TRACE = [
    "sources",
    "index_files",
    "uploaded_names",
    "file_names",
    "urls",
    "index_urls",
    "merge_files",
    "extend_choices",
    "merge_graph",
    "selection",
    "update",
    "append_history",
]
