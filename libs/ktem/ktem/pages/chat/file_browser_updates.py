"""Deliver authorized file presentation through the browser's intent boundary."""

import gradio as gr

CAPTURE_FILES_JS = """function (...args) {
    return [...args.slice(0, 6), window.maraFileBrowserRefresh.captureFiles(INDEX_ID)];
}"""
APPLY_FILES_JS = """function (payload, filter, selected, conversation) {
    return window.maraFileBrowserRefresh.applyFiles(payload, filter, selected, conversation);
}"""
CAPTURE_SELECTOR_JS = """function (...args) {
    return [...args.slice(0, 2), window.maraFileBrowserRefresh.captureSelector(INDEX_ID, INDEX_CHANGED), args[3]];
}"""
APPLY_SELECTOR_JS = """function (payload, selected) {
    return window.maraFileBrowserRefresh.applySelector(payload, selected);
}"""
CAPTURE_UPLOAD_JS = """function (...args) {
    return [...args.slice(0, 4), window.maraFileBrowserRefresh.captureUpload('CONTROL'), args[5]];
}"""
APPLY_UPLOAD_RESET_JS = """function (payload) {
    return window.maraFileBrowserRefresh.applyUploadReset(payload);
}"""
APPLY_UPLOAD_SELECTION_JS = """function (payload, conversation) {
    return window.maraFileBrowserRefresh.applyUploadSelection(payload, conversation);
}"""
CAPTURE_SELECTION_JS = """function (file_id) {
    return [file_id, window.maraFileBrowserRefresh.captureFileSelection(INDEX_ID)];
}"""
APPLY_SELECTION_JS = """function (payload) {
    return window.maraFileBrowserRefresh.applyFileSelection(payload);
}"""


def file_selection_result(callback):
    def select(file_id, stamp):
        return {"file_id": file_id, "stamp": stamp, "outputs": callback(file_id)}

    select.__name__ = callback.__name__
    return select


def quick_upload_result(callback):
    def index(
        source, reindex, settings, user_id, stamp, conversation, request: gr.Request
    ):
        ids = callback(source, reindex, settings, user_id, request=request)
        return ids, {"stamp": stamp, "conversation": conversation, "ids": ids}

    index.__name__ = callback.__name__
    return index


def file_browser_result(callback):
    def refresh(
        conversation_id,
        user_id,
        choices,
        selected,
        graph_ids,
        filter_text,
        stamp,
        request: gr.Request,
    ):
        outputs = callback(
            conversation_id,
            user_id,
            choices,
            selected,
            graph_ids,
            filter_text,
            request=request,
        )
        return {
            "stamp": stamp,
            "conversation": conversation_id,
            "selected": selected,
            "filter": filter_text,
            "outputs": outputs,
        }

    refresh.__name__ = callback.__name__
    return refresh


def file_selector_result(callback, apply_choices):
    def load_files(selected, user_id, stamp, applied, request: gr.Request):
        update, options = callback(selected, user_id, request=request)
        apply_choices(stamp, options, applied)
        return {
            "stamp": stamp,
            "selected": selected,
            "update": update,
            "options": options,
            "available_ids": [file_id for _, file_id in options],
        }

    load_files.__name__ = callback.__name__
    return load_files


def chat_file_refresh_event(page):
    return {
        "fn": file_browser_result(page.refresh_chat_file_list),
        "inputs": [
            page.chat_control.conversation_id,
            page._app.user_id,
            page.first_selector_choices,
            page._indices_input[1],
            page._graph_source_ids,
            page.chat_file_filter,
            page._file_browser_stamp,
        ],
        "outputs": [page._file_browser_result],
        "js": CAPTURE_FILES_JS.replace("INDEX_ID", str(page.file_index.id)),
        "show_progress": "hidden",
    }


def bind_file_browser_result(page):
    page._file_browser_result.change(
        fn=None,
        inputs=[
            page._file_browser_result,
            page.chat_file_filter,
            page._indices_input[1],
            page.chat_control.conversation,
        ],
        outputs=[
            page.chat_file_rows,
            page.chat_file_list,
            page.chat_selected_file,
            page.workbench_file_summary,
        ],
        js=APPLY_FILES_JS,
        show_progress="hidden",
    )


def bind_file_selection_result(page):
    page._chat_file_click.change(
        fn=file_selection_result(page.select_chat_file),
        inputs=[page._chat_file_click, page._file_browser_stamp],
        outputs=[page._file_browser_selection_result],
        js=CAPTURE_SELECTION_JS.replace("INDEX_ID", str(page.file_index.id)),
        show_progress="hidden",
    )
    page._file_browser_selection_result.change(
        fn=None,
        inputs=[page._file_browser_selection_result],
        outputs=[
            page._indices_input[0],
            page._indices_input[1],
            page._chat_file_click,
            page._file_browser_selection_applied,
        ],
        js=APPLY_SELECTION_JS,
        show_progress="hidden",
    )
