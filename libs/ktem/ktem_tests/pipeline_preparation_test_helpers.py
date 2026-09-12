"""Specific resource spies for the pipeline preparation contract."""

from __future__ import annotations

from collections import Counter
from functools import wraps
from types import SimpleNamespace
from typing import Any, cast

import ktem.docqa.runtime as runtime_module
from ktem.docqa.runtime import DocQARuntime


class PreparationProbe:
    def __init__(self, monkeypatch) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.counts: Counter[str] = Counter()
        self.fail_at: tuple[str, int] | None = None
        self.failure = RuntimeError("preparation resource failed")
        self.pipeline = SimpleNamespace()
        self.settings = {
            "reasoning.use": "mara",
            "reasoning.options.mara.llm": "saved-model",
            "reasoning.options.mara.qa_prompt": "Saved prompt  ",
            "nested": {"values": ["settings"]},
        }
        self.resolved_ids = ["file-b", "file-a"]
        self.page_text = "Page context"
        self.file_name = "Report.PDF"
        self.local_graph = {"graph_index": {"nodes": ["local"]}}
        self.local_elements = [self.element("local", "Local element")]
        self.retrievers = [object(), object(), object()]
        self.web_retriever = object()
        self.preview = PreviewProbe(self)
        self.file_index = IndexProbe(self, 9, self.retrievers[:2])
        self.other_index = IndexProbe(self, 4, self.retrievers[2:])
        self.runtime = cast(Any, object.__new__(DocQARuntime))
        self.runtime._app = SimpleNamespace(
            index_manager=SimpleNamespace(indices=[self.file_index, self.other_index])
        )
        self.runtime._preview = self.preview
        self.runtime.file_index = self.file_index
        self.runtime._resolve_user_id = self.resolve_user_id
        self.runtime.load_settings = self.load_settings
        self.runtime._web_search_cls = self.web_search
        self._install_spies(monkeypatch)

    @staticmethod
    def element(element_id, text):
        return {
            "evidence_id": f"element:file-b:2:{element_id}",
            "file_id": "file-b",
            "page_label": "2",
            "element_id": element_id,
            "modality": "table",
            "text": text,
        }

    @property
    def names(self):
        return [name for name, _args, _kwargs in self.calls]

    def record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        self.counts[name] += 1
        if self.fail_at == (name, self.counts[name]):
            raise self.failure

    def call(self, name, occurrence=1):
        return [call for call in self.calls if call[0] == name][occurrence - 1]

    def resolve_user_id(self, user_id):
        self.record("resolve_user", user_id)
        return "principal"

    def load_settings(self, user_id):
        self.record("load_settings", user_id)
        return self.settings

    def web_search(self):
        self.record("web_search")
        return self.web_retriever

    def _install_spies(self, monkeypatch):
        probe = self

        class Reasoning:
            @staticmethod
            def get_info():
                probe.record("get_info")
                return {"id": "mara"}

            @staticmethod
            def get_pipeline(settings, state, retrievers):
                probe.record("get_pipeline", settings, state, retrievers)
                return probe.pipeline

        monkeypatch.setattr(runtime_module, "reasonings", {"mara": Reasoning})
        self.reasoning = Reasoning
        for owner, name, event in (
            (runtime_module._pipeline, "apply_request_setting_overrides", "overrides"),
            (runtime_module._pipeline, "build_reasoning_state", "reasoning_state"),
            (runtime_module._runtime_preview, "resolve_active_source", "active_source"),
            (runtime_module._runtime_preview, "resolve_page_text", "page_text"),
            (runtime_module._runtime_preview, "validate_sources", "validate_graph"),
            (runtime_module, "_apply_request_page_image_records", "page_images"),
            (runtime_module, "_apply_multimodal_runtime_indexes", "multimodal"),
            (
                runtime_module,
                "_apply_request_element_index_records",
                "request_elements",
            ),
            (runtime_module._mara, "apply_request_context", "request_context"),
            (self.runtime, "_normalize_page_number", "normalize_page"),
            (self.runtime, "_normalize_qa_scope", "normalize_scope"),
            (self.runtime, "_normalize_selected_file_ids", "normalize_graph"),
            (self.runtime, "_selected_file_records_for_retrieval", "selected_records"),
        ):
            monkeypatch.setattr(owner, name, self._wrap(getattr(owner, name), event))
        monkeypatch.setattr(
            runtime_module._runtime_elements,
            "element_index_records_for_selected_files",
            self.elements,
        )
        monkeypatch.setattr(
            runtime_module._runtime_graph,
            "graph_context_for_selected_files",
            self.graph,
        )

    def _wrap(self, function, event):
        @wraps(function)
        def wrapped(*args, **kwargs):
            self.record(event, *args, **kwargs)
            return function(*args, **kwargs)

        return wrapped

    def elements(self, file_index, file_ids):
        self.record("local_elements", file_index, file_ids)
        return self.local_elements

    def graph(self, file_index, file_ids):
        self.record("local_graph", file_index, file_ids)
        return self.local_graph

    def prepare(self, request):
        return self.runtime._prepare_pipeline(request)


class IndexProbe:
    def __init__(self, probe, index_id, retrievers):
        self.probe = probe
        self.id = index_id
        self.retrievers = retrievers

    def get_retriever_pipelines(self, settings, user_id, selected_input):
        self.probe.record(f"retriever:{self.id}", settings, user_id, selected_input)
        return self.retrievers

    def resolve_selected_ids(self, user_id, selected_input):
        self.probe.record("selected_ids", user_id, selected_input)
        return self.probe.resolved_ids


class PreviewProbe:
    def __init__(self, probe):
        self.probe = probe

    def resolve_file_name(self, file_id, *, user_id):
        self.probe.record("file_name", file_id, user_id=user_id)
        return self.probe.file_name

    def resolve_selected_file(self, file_ids, *, user_id):
        self.probe.record("infer_source", file_ids, user_id=user_id)
        return "file-b", self.probe.file_name, "/owned/Report.PDF"

    def get_page_context_text(self, file_id, file_name, page_number, *, user_id):
        self.probe.record("read_page", file_id, file_name, page_number, user_id=user_id)
        return self.probe.page_text

    def resolve_sources(self, file_ids, *, user_id, strict):
        self.probe.record("sources", file_ids, user_id=user_id, strict=strict)
        return [
            SimpleNamespace(
                file_id=file_id, name=self.probe.file_name, path="/owned/source"
            )
            for file_id in file_ids
        ]
