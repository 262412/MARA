from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import ktem.index.file.ui as file_ui_module
import pandas as pd
import pytest
from ktem.index.file._deletion import FileIndexDeletionController
from ktem.index.file._events import (
    register_file_index_events,
    register_quick_upload_events,
)
from ktem.index.file._listing import (
    extract_conversation_file_ids,
    format_conversation_scope,
    normalize_selected_ids_from_payload,
)
from ktem.index.file.pipelines import IndexDocumentPipeline
from ktem.index.file.ui import FileIndexPage


class _FakeChain:
    def __init__(self, action_log):
        self._action_log = action_log

    def then(self, **kwargs):
        self._action_log.append(("then", kwargs))
        return self

    def success(self, **kwargs):
        self._action_log.append(("success", kwargs))
        return self


class _FakeComponent:
    def __init__(self):
        self.calls = []

    def click(self, **kwargs):
        self.calls.append(("click", kwargs))
        return _FakeChain(self.calls)

    def select(self, **kwargs):
        self.calls.append(("select", kwargs))
        return _FakeChain(self.calls)

    def submit(self, **kwargs):
        self.calls.append(("submit", kwargs))
        return _FakeChain(self.calls)

    def upload(self, **kwargs):
        self.calls.append(("upload", kwargs))
        return _FakeChain(self.calls)

    def input(self, *args, **kwargs):
        self.calls.append(("input", {"args": args, "kwargs": kwargs}))
        return _FakeChain(self.calls)


class _DeletionSpy(FileIndexDeletionController):
    def __init__(self):
        super().__init__(index=SimpleNamespace(), selected_panel_false="Selected")
        self.deleted_ids: list[str] = []

    def delete_event(self, file_id):
        self.deleted_ids.append(file_id)


class _ListingControllerStub:
    @staticmethod
    def list_file(user_id, name_pattern=""):
        return "rows", "frame"

    @staticmethod
    def list_file_names(file_list_state):
        return "choices", file_list_state


def _build_page(index_id=7, with_chat_refresh=False):
    page = SimpleNamespace()
    selector_ui = SimpleNamespace(selector=object(), mode=object())
    page.selected_panel_false = "Selected file: (please select above)"
    page.delete_button = _FakeComponent()
    page.deselect_button = _FakeComponent()
    page.chat_button = _FakeComponent()
    page.download_all_button = _FakeComponent()
    page.delete_all_button = _FakeComponent()
    page.delete_all_button_confirm = _FakeComponent()
    page.delete_all_button_cancel = _FakeComponent()
    page.download_single_button = _FakeComponent()
    page.upload_button = _FakeComponent()
    page.file_list = _FakeComponent()
    page.group_list = _FakeComponent()
    page.group_list_state = object()
    page.group_add_button = _FakeComponent()
    page.group_chat_button = _FakeComponent()
    page.group_close_button = _FakeComponent()
    page.group_delete_button = _FakeComponent()
    page.group_save_button = _FakeComponent()
    page.btn_close_upload_progress_panel = _FakeComponent()
    page.filter = _FakeComponent()

    page.delete_event = object()
    page.list_file = object()
    page.file_selected = object()
    page.set_file_id_selector = object()
    page.set_group_id_selector = object()
    page.download_all_files = object()
    page.show_delete_all_confirm = object()
    page.delete_all_files = object()
    page.download_single_file = object()
    page.download_single_file_simple = object()
    page.snapshot_source_ids = object()
    page.index_fn = object()
    page.collect_new_source_ids = object()
    page.interact_file_list = object()
    page.interact_group_list = object()
    page.list_group = object()
    page.save_group = object()
    page.delete_group = object()
    page.index_fn_file_with_default_loaders = object()
    page.index_fn_url_with_default_loaders = object()

    page.selected_file_id = object()
    page.selected_panel = object()
    page.file_list_state = object()
    page.chunks = object()
    page.is_zipped_state = object()
    page.upload_progress_panel = object()
    page.upload_before_source_ids = object()
    page.upload_result = object()
    page.upload_info = object()
    page.urls = object()
    page.files = object()
    page.reindex = object()
    page.upload_new_source_ids = object()
    page._group_info_panel = object()
    page.group_name = object()
    page.group_files = object()
    page.selected_group_id = object()
    page.group_label = object()

    page._index = SimpleNamespace(
        id=index_id,
        get_selector_component_ui=lambda: selector_ui,
    )
    page._app = SimpleNamespace(
        user_id=object(),
        settings_state=object(),
        tabs=object(),
        get_event=lambda _name: [{"fn": "public-event"}],
        chat_page=None,
    )

    if with_chat_refresh:
        page._app.chat_page = SimpleNamespace(
            quick_file_upload=_FakeComponent(),
            quick_file_upload_status=object(),
            quick_urls=_FakeComponent(),
            _indices_input=[object(), object()],
            _graph_source_ids=object(),
            first_selector_choices=object(),
            chat_file_filter=object(),
            chat_file_rows=object(),
            chat_file_list=object(),
            chat_selected_file=object(),
            workbench_file_summary=object(),
            plot_panel=object(),
            state_plot_panel=object(),
            knowledge_graph_status=object(),
            knowledge_graph=object(),
            _active_file_id=object(),
            chat_control=SimpleNamespace(conversation_id=object()),
            merge_graph_source_ids=object(),
            refresh_chat_file_list=object(),
            show_knowledge_graph_loading=object(),
            refresh_knowledge_graph=object(),
            persist_conversation_source_scope=object(),
        )

    return page


def test_normalize_selected_ids_from_payload_deduplicates_and_skips_placeholders():
    payload = {
        "1": ["select", ["file-1", "file-2"], "default"],
        "2": [["file-2", "file-3"], "all", ""],
        "3": {"ignored": True},
    }

    assert normalize_selected_ids_from_payload(payload) == [
        "file-1",
        "file-2",
        "default",
        "file-3",
    ]


def test_extract_conversation_file_ids_prefers_graph_source_ids():
    data_source = {
        "graph_source_ids": ["file-2", "file-1", "file-2", "", "   "],
        "selected": {"1": ["select", ["ignored-file"]]},
    }

    assert extract_conversation_file_ids(data_source) == ["file-2", "file-1"]


def test_extract_conversation_file_ids_falls_back_to_selected_payload():
    data_source = {
        "selected": {"1": ["select", ["file-1", "file-2"], "all"]},
    }

    assert extract_conversation_file_ids(data_source) == ["file-1", "file-2"]


def test_format_conversation_scope_compacts_long_lists():
    assert format_conversation_scope([]) == "-"
    assert format_conversation_scope(["Chat A", "Chat B"]) == "Chat A, Chat B"
    assert (
        format_conversation_scope(["Chat A", "Chat B", "Chat C"])
        == "Chat A, Chat B (+1)"
    )


def test_delete_all_files_skips_placeholder_rows():
    controller = _DeletionSpy()

    controller.delete_all_files(pd.DataFrame({"id": ["file-1", "-", None, "file-2"]}))

    assert controller.deleted_ids == ["file-1", "file-2"]


def test_page_label_sort_key_handles_mixed_page_label_types():
    docs = [
        SimpleNamespace(metadata={"page_label": "appendix"}),
        SimpleNamespace(metadata={"page_label": None}),
        SimpleNamespace(metadata={"page_label": "2"}),
        SimpleNamespace(metadata={"page_label": 1.0}),
        SimpleNamespace(metadata={}),
    ]

    page_label_sort_key = getattr(file_ui_module, "_page_label_sort_key")
    sorted_docs = sorted(docs, key=page_label_sort_key)

    assert [doc.metadata.get("page_label") for doc in sorted_docs] == [
        1.0,
        "2",
        "appendix",
        None,
        None,
    ]


def test_register_file_index_events_wires_delete_chat_and_upload_flows():
    page = _build_page(index_id=9)

    register_file_index_events(
        page,
        demo_mode=False,
        sso_enabled=False,
    )

    delete_chain = page.delete_button.calls
    assert delete_chain[0] == (
        "click",
        {
            "fn": page.delete_event,
            "inputs": [page.selected_file_id],
            "outputs": None,
        },
    )
    assert [entry[1]["fn"] for entry in delete_chain[1:4]] == [
        delete_chain[1][1]["fn"],
        page.list_file,
        page.file_selected,
    ]
    assert delete_chain[4] == ("then", {"fn": "public-event"})

    assert page.chat_button.calls[0] == (
        "click",
        {
            "fn": page.set_file_id_selector,
            "inputs": [page.selected_file_id],
            "outputs": [
                page._index.get_selector_component_ui().selector,
                page._index.get_selector_component_ui().mode,
                page._app.tabs,
            ],
        },
    )

    upload_chain = page.upload_button.calls
    assert upload_chain[1][1]["fn"] == page.snapshot_source_ids
    assert upload_chain[2][1]["fn"] == page.index_fn
    assert upload_chain[4][1]["fn"] == page.collect_new_source_ids
    assert upload_chain[5][1]["fn"] == page.list_file
    assert upload_chain[6] == ("then", {"fn": "public-event"})


def test_register_file_index_events_keeps_graph_refresh_tail_wired():
    page = _build_page(index_id=1, with_chat_refresh=True)

    register_file_index_events(
        page,
        demo_mode=False,
        sso_enabled=False,
    )

    upload_chain = page.upload_button.calls
    assert [entry[1]["fn"] for entry in upload_chain[7:11]] == [
        page._app.chat_page.merge_graph_source_ids,
        page._app.chat_page.persist_conversation_source_scope,
        page._app.chat_page.refresh_chat_file_list,
        page._app.chat_page.refresh_knowledge_graph,
    ]
    assert upload_chain[7][1]["inputs"] == [
        page._app.chat_page._graph_source_ids,
        page.upload_new_source_ids,
    ]
    assert upload_chain[8][1]["inputs"] == [
        page._app.chat_page.chat_control.conversation_id,
        page._app.user_id,
        page._app.chat_page._graph_source_ids,
    ]
    assert upload_chain[9][1]["outputs"] == [
        page._app.chat_page.chat_file_rows,
        page._app.chat_page.chat_file_list,
        page._app.chat_page.chat_selected_file,
        page._app.chat_page.workbench_file_summary,
    ]
    assert upload_chain[10][1]["inputs"] == [
        page._app.chat_page.chat_control.conversation_id,
        page._app.chat_page._graph_source_ids,
        page._app.chat_page._active_file_id,
        page._app.chat_page._indices_input[1],
    ]


def test_register_quick_upload_events_wires_file_and_url_uploads():
    page = _build_page(index_id=1, with_chat_refresh=True)

    register_quick_upload_events(
        page,
        demo_mode=False,
        chat_input_focus_js="focus-js",
    )

    file_upload_chain = page._app.chat_page.quick_file_upload.calls
    assert file_upload_chain[0][0] == "upload"
    assert file_upload_chain[1][1]["fn"] == page.index_fn_file_with_default_loaders
    assert file_upload_chain[3] == ("then", {"fn": "public-event"})
    assert (
        page._app.chat_page.quick_urls.calls[1][1]["fn"]
        == page.index_fn_url_with_default_loaders
    )


def test_file_index_page_listing_wrappers_delegate_to_active_helpers(monkeypatch):
    page = cast(Any, FileIndexPage.__new__(FileIndexPage))
    page._listing_controller = cast(Any, _ListingControllerStub())
    file_index_page_cls = cast(Any, FileIndexPage)

    monkeypatch.setattr(
        file_ui_module,
        "normalize_selected_ids_from_payload",
        lambda payload: ["normalized", payload],
    )
    monkeypatch.setattr(
        file_ui_module,
        "extract_conversation_file_ids",
        lambda data_source: ["extracted", data_source],
    )
    monkeypatch.setattr(
        file_ui_module,
        "format_conversation_scope",
        lambda names: f"scope:{','.join(names)}",
    )

    assert page.list_file("user-1", "budget") == ("rows", "frame")
    assert page.list_file_names([{"id": "1"}]) == ("choices", [{"id": "1"}])
    assert file_index_page_cls._normalize_selected_ids_from_payload({"a": 1}) == [
        "normalized",
        {"a": 1},
    ]
    assert page._extract_conversation_file_ids({"selected": []}) == [
        "extracted",
        {"selected": []},
    ]
    assert file_index_page_cls._format_conversation_scope(["Chat A", "Chat B"]) == (
        "scope:Chat A,Chat B"
    )


def test_file_index_page_event_wrapper_methods_delegate_to_registrars(monkeypatch):
    page = FileIndexPage.__new__(FileIndexPage)
    calls: list[tuple[str, object, dict[str, object]]] = []

    monkeypatch.setattr(
        file_ui_module,
        "register_quick_upload_events",
        lambda target, **kwargs: calls.append(("quick", target, kwargs)),
    )
    monkeypatch.setattr(
        file_ui_module,
        "register_file_index_events",
        lambda target, **kwargs: calls.append(("events", target, kwargs)),
    )

    FileIndexPage.on_register_events(page)

    assert calls == [
        (
            "quick",
            page,
            {
                "demo_mode": file_ui_module.KH_DEMO_MODE,
                "chat_input_focus_js": file_ui_module.chat_input_focus_js_with_submit,
            },
        ),
        (
            "events",
            page,
            {
                "demo_mode": file_ui_module.KH_DEMO_MODE,
                "sso_enabled": file_ui_module.KH_SSO_ENABLED,
            },
        ),
    ]


def test_file_loader_settings_expose_mathpix_formula_ocr_mode():
    reader_mode = IndexDocumentPipeline.get_user_settings()["reader_mode"]

    values = [value for _label, value in reader_mode["choices"]]

    assert "mathpix" in values


def test_layout_preserving_docx_conversion_routes_indexing_to_pdf(
    monkeypatch, tmp_path
):
    source_path = tmp_path / "layout.docx"
    converted_path = tmp_path / "layout.pdf"
    source_path.write_bytes(b"docx")
    converted_path.write_bytes(b"pdf")

    monkeypatch.setattr(
        "ktem.index.file.pipelines.get_office_pdf_converter",
        lambda: SimpleNamespace(
            convert_to_pdf=lambda file_path, file_name: str(converted_path)
        ),
    )
    monkeypatch.setattr(
        "ktem.index.file.pipelines.is_valid_pdf",
        lambda path: Path(path) == converted_path,
    )

    pipeline = IndexDocumentPipeline(embedding=SimpleNamespace())
    parse_path, metadata = pipeline.prepare_layout_preserving_parse_file(source_path)

    assert parse_path == converted_path.resolve()
    assert metadata is not None
    assert metadata["converted_from_office"] is True
    assert metadata["layout_preserving_parse"] is True
    assert metadata["source_file_name"] == "layout.docx"
    assert metadata["converted_pdf_path"] == str(converted_path.resolve())


def test_layout_preserving_docx_conversion_fails_strictly(monkeypatch, tmp_path):
    source_path = tmp_path / "layout.docx"
    source_path.write_bytes(b"docx")

    monkeypatch.setattr(
        "ktem.index.file.pipelines.get_office_pdf_converter",
        lambda: SimpleNamespace(convert_to_pdf=lambda file_path, file_name: ""),
    )
    monkeypatch.setattr(
        "ktem.index.file.pipelines.settings.KH_OFFICE_TO_PDF_INDEXING_STRICT",
        True,
        raising=False,
    )

    pipeline = IndexDocumentPipeline(embedding=SimpleNamespace())
    with pytest.raises(RuntimeError, match="Failed to convert layout.docx to PDF"):
        pipeline.prepare_layout_preserving_parse_file(source_path)
