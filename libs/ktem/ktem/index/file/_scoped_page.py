from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Any, TypeAlias

import gradio as gr
from theflow.settings import settings as flowsettings

from ._group_service import GroupServiceError
from ._identity import MISSING_REQUEST, resolve_file_index_user_id
from ._selection_service import FileSelectionError

DOWNLOAD_MESSAGE = "Start download"
Request: TypeAlias = gr.Request


class ScopedFileIndexPageMixin:
    _listing_controller: Any

    def _get_file_selection_service(self) -> Any:
        raise NotImplementedError

    def _get_group_service(self) -> Any:
        raise NotImplementedError

    def snapshot_source_ids(
        self,
        user_id,
        request: Request = MISSING_REQUEST,
    ) -> list[str]:
        user_id = resolve_file_index_user_id(user_id, request)
        return self._listing_controller.snapshot_source_ids(user_id)

    def collect_new_source_ids(
        self,
        before_source_ids,
        user_id,
        request: Request = MISSING_REQUEST,
    ) -> list[str]:
        user_id = resolve_file_index_user_id(user_id, request)
        return self._listing_controller.collect_new_source_ids(
            before_source_ids,
            user_id,
        )

    def file_selected(
        self,
        file_id,
        user_id=None,
        request: Request = MISSING_REQUEST,
    ):
        chunks = ""
        if file_id is not None:
            user_id = resolve_file_index_user_id(user_id, request)
            try:
                chunks = self._get_file_selection_service().render_chunks(
                    file_id,
                    user_id,
                )
            except FileSelectionError as exc:
                raise gr.Error(str(exc)) from exc
        return (
            gr.update(value=chunks, visible=file_id is not None),
            gr.update(visible=file_id is not None),
            gr.update(visible=file_id is not None),
            gr.update(visible=file_id is not None),
            gr.update(visible=file_id is not None),
        )

    def download_single_file(
        self,
        is_zipped_state,
        file_id,
        user_id,
        request: Request = MISSING_REQUEST,
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        target_file_name = self._scoped_source_name(file_id, user_id)
        zip_files = self._download_outputs_for(target_file_name.stem)
        zip_file_path = os.path.join(
            flowsettings.KH_ZIP_OUTPUT_DIR,
            target_file_name.stem,
        )
        with zipfile.ZipFile(f"{zip_file_path}.zip", "w") as archive:
            for file_path in zip_files:
                archive.write(file_path, arcname=os.path.basename(file_path))

        value = None if is_zipped_state else f"{zip_file_path}.zip"
        label = "Download" if is_zipped_state else DOWNLOAD_MESSAGE
        return not is_zipped_state, gr.DownloadButton(label=label, value=value)

    def download_single_file_simple(
        self,
        is_zipped_state,
        file_html,
        file_id,
        user_id,
        request: Request = MISSING_REQUEST,
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        target_file_name = self._scoped_source_name(file_id, user_id)
        output_file_path = os.path.join(
            flowsettings.KH_ZIP_OUTPUT_DIR,
            target_file_name.stem + ".html",
        )
        with open(output_file_path, "w", encoding="utf-8") as output_file:
            output_file.write(file_html)

        value = None if is_zipped_state else output_file_path
        label = "Download" if is_zipped_state else DOWNLOAD_MESSAGE
        return not is_zipped_state, gr.DownloadButton(label=label, value=value)

    def _scoped_source_name(self, file_id, user_id) -> Path:
        try:
            return Path(
                self._get_file_selection_service().source_name(file_id, user_id)
            )
        except FileSelectionError as exc:
            raise gr.Error(str(exc)) from exc

    @staticmethod
    def _download_outputs_for(file_stem: str) -> list[str]:
        paths: list[str] = []
        for directory in (
            flowsettings.KH_CHUNKS_OUTPUT_DIR,
            flowsettings.KH_MARKDOWN_OUTPUT_DIR,
        ):
            for file_name in os.listdir(directory):
                if file_stem in file_name:
                    paths.append(os.path.join(directory, file_name))
        return paths

    def list_file(
        self,
        user_id,
        request: Request = MISSING_REQUEST,
        name_pattern="",
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        return self._listing_controller.list_file(user_id, name_pattern)

    def list_group(
        self,
        user_id,
        file_list,
        request: Request = MISSING_REQUEST,
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        return self._get_group_service().list_groups(user_id, file_list)

    def set_group_id_selector(
        self,
        selected_group_id,
        user_id=None,
        request: Request = MISSING_REQUEST,
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        file_ids = self._get_group_service().selected_file_ids(
            selected_group_id,
            user_id,
        )
        return [file_ids, "select", gr.Tabs(selected="chat-tab")]

    def save_group(
        self,
        group_id,
        group_name,
        group_files,
        user_id,
        request: Request = MISSING_REQUEST,
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        try:
            group_id = self._get_group_service().save_group(
                group_id,
                group_name,
                group_files,
                user_id,
            )
        except GroupServiceError as exc:
            raise gr.Error(str(exc)) from exc
        gr.Info(f"Group {group_name} has been saved")
        return group_id

    def delete_group(
        self,
        group_id,
        user_id=None,
        request: Request = MISSING_REQUEST,
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        try:
            group_name = self._get_group_service().delete_group(group_id, user_id)
        except GroupServiceError as exc:
            raise gr.Error(str(exc)) from exc
        gr.Info(f"Group {group_name} has been deleted")
        return None


__all__ = ["ScopedFileIndexPageMixin"]
