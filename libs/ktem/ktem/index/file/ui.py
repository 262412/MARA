import os
import tempfile
import zipfile
from pathlib import Path
from typing import Generator, TypeAlias

import gradio as gr
from gradio.data_classes import FileData
from gradio.utils import NamedString
from ktem.app import BasePage
from ktem.db.engine import engine
from theflow.settings import settings as flowsettings

from ...utils.rate_limit import check_rate_limit
from ._deletion import FileIndexDeletionController
from ._events import register_file_index_events, register_quick_upload_events
from ._group_service import FileGroupService
from ._identity import MISSING_REQUEST, resolve_file_index_user_id
from ._indexing_service import FileIndexingService
from ._listing import (
    FileIndexListingController,
    extract_conversation_file_ids,
    format_conversation_scope,
    normalize_selected_ids_from_payload,
)
from ._scoped_page import ScopedFileIndexPageMixin
from ._selection_service import FileSelectionService
from ._selector_ui import FileSelector
from .archive import extract_supported_zip_files
from .utils import download_arxiv_pdf, is_arxiv_url

__all__ = ["DirectoryUpload", "File", "FileIndexPage", "FileSelector"]
KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)
KH_SSO_ENABLED = getattr(flowsettings, "KH_SSO_ENABLED", False)
DOWNLOAD_MESSAGE = "Start download"
Request: TypeAlias = gr.Request


def _page_label_sort_key(doc):
    page_label = getattr(doc, "metadata", {}).get("page_label")
    if page_label in (None, ""):
        return (2, float("inf"), "")

    page_label_text = str(page_label)
    try:
        return (0, float(page_label_text), page_label_text)
    except (TypeError, ValueError):
        return (1, float("inf"), page_label_text)


chat_input_focus_js = """
function() {
    let chatInput = document.querySelector("#chat-input textarea");
    chatInput.focus();
}
"""

chat_input_focus_js_with_submit = """
function() {
    let chatInput = document.querySelector("#chat-input textarea");
    chatInput.focus();
}
"""


class File(gr.File):
    """Subclass from gr.File to maintain the original filename

    The issue happens when user uploads file with name like: !@#$%%^&*().pdf
    """

    def _process_single_file(self, f: FileData) -> NamedString | bytes:
        file_name = f.path
        if self.type == "filepath":
            if f.orig_name and Path(file_name).name != f.orig_name:
                file_name = str(Path(file_name).parent / f.orig_name)
                # Check if destination file already exists before renaming
                if os.path.exists(file_name):
                    # Remove existing file to avoid FileExistsError
                    os.remove(file_name)
                os.rename(f.path, file_name)
            file = tempfile.NamedTemporaryFile(delete=False, dir=self.GRADIO_CACHE)
            file.name = file_name
            return NamedString(file_name)
        elif self.type == "binary":
            with open(file_name, "rb") as file_data:
                return file_data.read()
        else:
            raise ValueError(
                "Unknown type: "
                + str(type)
                + ". Please choose from: 'filepath', 'binary'."
            )


class DirectoryUpload(BasePage):
    def __init__(self, app, index):
        super().__init__(app)
        self._index = index
        self._supported_file_types_str = self._index.config.get(
            "supported_file_types", ""
        )
        self._supported_file_types = [
            each.strip() for each in self._supported_file_types_str.split(",")
        ]
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Accordion(label="Directory upload", open=False):
            gr.Markdown(f"Supported file types: {self._supported_file_types_str}")
            self.path = gr.Textbox(
                placeholder="Directory path...", lines=1, max_lines=1, container=False
            )
            with gr.Accordion("Advanced indexing options", open=False):
                with gr.Row():
                    self.reindex = gr.Checkbox(
                        value=False, label="Force reindex file", container=False
                    )

            self.upload_button = gr.Button("Upload and Index")


class FileIndexPage(ScopedFileIndexPageMixin, BasePage):
    def __init__(self, app, index):
        super().__init__(app)
        self._index = index
        self._supported_file_types_str = self._index.config.get(
            "supported_file_types", ""
        )
        self._supported_file_types = [
            each.strip() for each in self._supported_file_types_str.split(",")
        ]
        self.selected_panel_false = "Selected file: (please select above)"
        self.selected_panel_true = "Selected file: {name}"
        self._deletion_controller = FileIndexDeletionController(
            self._index, self.selected_panel_false
        )
        self._listing_controller = FileIndexListingController(
            self._index, self.format_size_human_readable
        )
        # TODO: on_building_ui is not correctly named if it's always called in
        # the constructor
        self.public_events = [f"onFileIndex{index.id}Changed"]

        if not KH_DEMO_MODE:
            self.on_building_ui()

    def upload_instruction(self) -> str:
        msgs = []
        if self._supported_file_types:
            msgs.append(f"- Supported file types: {self._supported_file_types_str}")

        if max_file_size := self._index.config.get("max_file_size", 0):
            msgs.append(f"- Maximum file size: {max_file_size} MB")

        if max_number_of_files := self._index.config.get("max_number_of_files", 0):
            msgs.append(f"- The index can have maximum {max_number_of_files} files")

        if msgs:
            return "\n".join(msgs)

        return ""

    def render_file_list(self):
        self.filter = gr.Textbox(
            value="",
            label="Filter by name:",
            info=(
                "(1) Case-insensitive. "
                "(2) Search with empty string to show all files."
            ),
        )
        self.file_list_state = gr.State(value=None)
        self.file_list = gr.DataFrame(
            headers=[
                "id",
                "name",
                "size",
                "tokens",
                "loader",
                "date_created",
            ],
            interactive=False,
            wrap=True,
            elem_id="file_list_view",
        )

        with gr.Row():

            self.chat_button = gr.Button(
                "Go to Chat",
                visible=False,
            )
            self.is_zipped_state = gr.State(value=False)
            self.download_single_button = gr.DownloadButton(
                "Download",
                visible=False,
            )
            self.delete_button = gr.Button(
                "Delete",
                variant="stop",
                visible=False,
            )
            self.deselect_button = gr.Button(
                "Close",
                visible=False,
            )

        with gr.Row() as self.selection_info:
            self.selected_file_id = gr.State(value=None)
            with gr.Column(scale=2):
                self.selected_panel = gr.Markdown(self.selected_panel_false)

        self.chunks = gr.HTML(visible=False)

        with gr.Accordion("Advance options", open=False):
            with gr.Row():
                if not KH_SSO_ENABLED:
                    self.download_all_button = gr.DownloadButton(
                        "Download all files",
                    )
                self.delete_all_button = gr.Button(
                    "Delete all files",
                    variant="stop",
                    visible=True,
                )
                self.delete_all_button_confirm = gr.Button(
                    "Confirm delete", variant="stop", visible=False
                )
                self.delete_all_button_cancel = gr.Button("Cancel", visible=False)

    def render_group_list(self):
        self.group_list_state = gr.State(value=None)
        self.group_list = gr.DataFrame(
            headers=[
                "id",
                "name",
                "files",
                "date_created",
            ],
            column_widths=[0, 25, 55, 20],
            interactive=False,
            wrap=False,
        )

        with gr.Row():
            self.group_add_button = gr.Button(
                "Add",
                variant="primary",
            )
            self.group_chat_button = gr.Button(
                "Go to Chat",
                visible=False,
            )
            self.group_delete_button = gr.Button(
                "Delete",
                variant="stop",
                visible=False,
            )
            self.group_close_button = gr.Button(
                "Close",
                visible=False,
            )

        with gr.Column(visible=False) as self._group_info_panel:
            self.selected_group_id = gr.State(value=None)
            self.group_label = gr.Markdown()
            self.group_name = gr.Textbox(
                label="Group name",
                placeholder="Group name",
                lines=1,
                max_lines=1,
            )
            self.group_files = gr.Dropdown(
                label="Attached files",
                multiselect=True,
            )
            self.group_save_button = gr.Button(
                "Save",
                variant="primary",
            )

    def on_building_ui(self):
        """Build the UI of the app"""
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Column() as self.upload:
                    with gr.Tab("Upload Files"):
                        self.files = File(
                            file_types=self._supported_file_types,
                            file_count="multiple",
                            container=True,
                            show_label=False,
                        )

                        msg = self.upload_instruction()
                        if msg:
                            gr.Markdown(msg)

                    with gr.Tab("Use Web Links"):
                        self.urls = gr.Textbox(
                            label="Input web URLs",
                            lines=8,
                        )
                        gr.Markdown("(separated by new line)")

                    with gr.Accordion("Advanced indexing options", open=False):
                        with gr.Row():
                            self.reindex = gr.Checkbox(
                                value=False, label="Force reindex file", container=False
                            )

                    self.upload_button = gr.Button(
                        "Upload and Index", variant="primary"
                    )

            with gr.Column(scale=4):
                with gr.Column(visible=False) as self.upload_progress_panel:
                    gr.Markdown("## Upload Progress")
                    with gr.Row():
                        self.upload_result = gr.Textbox(
                            lines=1, max_lines=20, label="Upload result"
                        )
                        self.upload_info = gr.Textbox(
                            lines=1, max_lines=20, label="Upload info"
                        )
                    self.btn_close_upload_progress_panel = gr.Button(
                        "Clear Upload Info and Close",
                        variant="secondary",
                        elem_classes=["right-button"],
                    )
                    self.upload_before_source_ids = gr.State(value=[])
                    self.upload_new_source_ids = gr.State(value=[])

                with gr.Tab("Files"):
                    self.render_file_list()

                with gr.Tab("Groups"):
                    self.render_group_list()

    def on_subscribe_public_events(self):
        """Subscribe to the declared public event of the app"""
        if KH_DEMO_MODE:
            return

        self._app.subscribe_event(
            name=f"onFileIndex{self._index.id}Changed",
            definition={
                "fn": self.list_file_names,
                "inputs": [self.file_list_state],
                "outputs": [self.group_files],
                "show_progress": "hidden",
            },
        )

        if self._app.f_user_management:
            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": self.list_file,
                    "inputs": [self._app.user_id],
                    "outputs": [self.file_list_state, self.file_list],
                    "show_progress": "hidden",
                },
            )
            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": self.list_group,
                    "inputs": [self._app.user_id, self.file_list_state],
                    "outputs": [self.group_list_state, self.group_list],
                    "show_progress": "hidden",
                },
            )
            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": self.list_file_names,
                    "inputs": [self.file_list_state],
                    "outputs": [self.group_files],
                    "show_progress": "hidden",
                },
            )
            self._app.subscribe_event(
                name="onSignOut",
                definition={
                    "fn": self.list_file,
                    "inputs": [self._app.user_id],
                    "outputs": [self.file_list_state, self.file_list],
                    "show_progress": "hidden",
                },
            )

    def _list_source_ids_for_user(self, user_id) -> list[str]:
        return self._listing_controller._list_source_ids_for_user(user_id)

    def _get_file_selection_service(self) -> FileSelectionService:
        return FileSelectionService(
            index=self._index,
            engine=engine,
            sort_key=_page_label_sort_key,
        )

    def delete_event(self, file_id, user_id, request: gr.Request):
        return self._deletion_controller.delete_event(file_id, user_id, request)

    def delete_no_event(self):
        return (
            gr.update(visible=True),
            gr.update(visible=False),
        )

    def download_all_files(self):
        if self._index.config.get("private", False):
            raise gr.Error("This feature is not available for private collection.")

        zip_files = []
        for file_name in os.listdir(flowsettings.KH_CHUNKS_OUTPUT_DIR):
            zip_files.append(os.path.join(flowsettings.KH_CHUNKS_OUTPUT_DIR, file_name))
        for file_name in os.listdir(flowsettings.KH_MARKDOWN_OUTPUT_DIR):
            zip_files.append(
                os.path.join(flowsettings.KH_MARKDOWN_OUTPUT_DIR, file_name)
            )
        zip_file_path = os.path.join(flowsettings.KH_ZIP_OUTPUT_DIR, "all")
        with zipfile.ZipFile(f"{zip_file_path}.zip", "w") as zipMe:
            for file in zip_files:
                arcname = Path(file)
                zipMe.write(file, arcname=arcname.name)
        return gr.DownloadButton(label=DOWNLOAD_MESSAGE, value=f"{zip_file_path}.zip")

    def delete_all_files(self, file_list, user_id, request: gr.Request):
        return self._deletion_controller.delete_all_files(file_list, user_id, request)

    def set_file_id_selector(self, selected_file_id):
        return self._deletion_controller.set_file_id_selector(selected_file_id)

    def show_delete_all_confirm(self, file_list):
        return self._deletion_controller.show_delete_all_confirm(file_list)

    def on_register_quick_uploads(self):
        register_quick_upload_events(
            self,
            demo_mode=KH_DEMO_MODE,
            chat_input_focus_js=chat_input_focus_js_with_submit,
        )

    def on_register_events(self):
        """Register all events to the app"""
        self.on_register_quick_uploads()
        register_file_index_events(
            self,
            demo_mode=KH_DEMO_MODE,
            sso_enabled=KH_SSO_ENABLED,
        )

    def _on_app_created(self):
        """Called when the app is created"""
        if KH_DEMO_MODE:
            return

        self._app.app.load(
            self.list_file,
            inputs=[self._app.user_id, self.filter],
            outputs=[self.file_list_state, self.file_list],
        ).then(
            self.list_group,
            inputs=[self._app.user_id, self.file_list_state],
            outputs=[self.group_list_state, self.group_list],
        ).then(
            self.list_file_names,
            inputs=[self.file_list_state],
            outputs=[self.group_files],
        )

    def _may_extract_zip(self, files, zip_dir: str):
        return self._get_indexing_service(zip_input_dir=zip_dir).extract_archives(files)

    def index_fn(
        self,
        files,
        urls,
        reindex: bool,
        settings,
        user_id,
        request: Request = MISSING_REQUEST,
    ) -> Generator[tuple[str, str], None, list[str] | None]:
        user_id = resolve_file_index_user_id(user_id, request)
        return (
            yield from self._get_indexing_service().index(
                files,
                urls,
                reindex=reindex,
                settings=settings,
                user_id=user_id,
            )
        )

    def index_fn_file_with_default_loaders(
        self,
        files,
        reindex: bool,
        settings,
        user_id,
        request: Request = MISSING_REQUEST,
    ) -> list["str"]:
        user_id = resolve_file_index_user_id(user_id, request)
        print("Overriding with default loaders")
        return self._get_indexing_service().index_files_with_default_loaders(
            files,
            reindex=reindex,
            settings=settings,
            user_id=user_id,
        )

    def index_fn_url_with_default_loaders(
        self,
        urls,
        reindex: bool,
        settings,
        user_id,
        request: Request = MISSING_REQUEST,
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        if KH_DEMO_MODE:
            check_rate_limit("file_upload", request)
        return self._get_indexing_service().index_urls_with_default_loaders(
            urls,
            reindex=reindex,
            settings=settings,
            user_id=user_id,
        )

    def index_files_from_dir(
        self,
        folder_path,
        reindex,
        settings,
        user_id,
        request: Request = MISSING_REQUEST,
    ) -> Generator[tuple[str, str], None, list[str] | None]:
        user_id = resolve_file_index_user_id(user_id, request)
        return (
            yield from self._get_indexing_service().index_directory(
                folder_path,
                reindex=reindex,
                settings=settings,
                user_id=user_id,
            )
        )

    def _get_indexing_service(self, *, zip_input_dir=None) -> FileIndexingService:
        return FileIndexingService(
            index=self._index,
            supported_file_types=self._supported_file_types,
            zip_input_dir=zip_input_dir or flowsettings.KH_ZIP_INPUT_DIR,
            engine=engine,
            demo_mode=KH_DEMO_MODE,
            notify=self._notify_index_status,
            archive_extractor=extract_supported_zip_files,
            arxiv_downloader=download_arxiv_pdf,
            arxiv_validator=is_arxiv_url,
        )

    @staticmethod
    def _notify_index_status(level: str, message: str) -> None:
        if level == "warning":
            gr.Warning(message)
        else:
            gr.Info(message)

    def format_size_human_readable(self, num: float | str, suffix="B"):
        try:
            num = float(num)
        except ValueError:
            return num

        for unit in ("", "K", "M", "G", "T", "P", "E", "Z"):
            if abs(num) < 1024.0:
                return f"{num:3.0f}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.0f}Yi{suffix}"

    @staticmethod
    def _normalize_selected_ids_from_payload(selected_payload) -> list[str]:
        return normalize_selected_ids_from_payload(selected_payload)

    def _extract_conversation_file_ids(self, data_source: dict | None) -> list[str]:
        return extract_conversation_file_ids(data_source)

    @staticmethod
    def _format_conversation_scope(conversation_names: list[str]) -> str:
        return format_conversation_scope(conversation_names)

    def list_file_names(self, file_list_state):
        return self._listing_controller.list_file_names(file_list_state)

    def _get_group_service(self) -> FileGroupService:
        return FileGroupService(index=self._index, engine=engine)

    def interact_file_list(self, list_files, ev: gr.SelectData):
        if ev.value == "-" and ev.index[0] == 0:
            gr.Info("No file is uploaded")
            return None, self.selected_panel_false

        if not ev.selected:
            return None, self.selected_panel_false

        return list_files["id"][ev.index[0]], self.selected_panel_true.format(
            name=list_files["name"][ev.index[0]]
        )

    def interact_group_list(self, list_groups, ev: gr.SelectData):
        selected_id = ev.index[0]
        if (not ev.value or ev.value == "-") and selected_id == 0:
            raise gr.Error("No group is selected")

        selected_item = list_groups[selected_id]
        selected_group_id = selected_item["id"]
        return (
            "### Group Information",
            selected_group_id,
            selected_item["name"],
            selected_item["files"],
        )

    def validate_files(self, files: list[str]):
        return self._get_indexing_service().validate_files(files)

    def validate_urls(self, urls: list[str]):
        return self._get_indexing_service().validate_urls(urls)
