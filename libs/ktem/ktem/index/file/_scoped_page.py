from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, TypeAlias

import gradio as gr
from theflow.settings import settings as flowsettings

from kotaemon.artifact_namespace import (
    ArtifactNamespaceError,
    isolated_output_path,
    load_manifest_artifacts,
)

from ._group_service import GroupServiceError
from ._identity import MISSING_REQUEST, resolve_file_index_user_id
from ._selection_service import FileSelectionError

DOWNLOAD_MESSAGE = "Start download"
DOWNLOAD_UNAVAILABLE_MESSAGE = (
    "File export is unavailable; reindex the file and try again."
)
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
        self._authorize_download(file_id, user_id)
        try:
            artifacts = load_manifest_artifacts(
                file_id,
                {
                    "chunks": flowsettings.KH_CHUNKS_OUTPUT_DIR,
                    "markdown": flowsettings.KH_MARKDOWN_OUTPUT_DIR,
                },
                flowsettings.KH_ZIP_OUTPUT_DIR,
            )
            zip_file_path = isolated_output_path(
                flowsettings.KH_ZIP_OUTPUT_DIR,
                file_id,
                ".zip",
            )
            temporary_path = zip_file_path.with_suffix(".zip.tmp")
            with zipfile.ZipFile(temporary_path, "x") as archive:
                for artifact in artifacts:
                    archive.write(artifact.path, arcname=artifact.archive_name)
            temporary_path.replace(zip_file_path)
        except (ArtifactNamespaceError, OSError, zipfile.BadZipFile) as exc:
            raise gr.Error(DOWNLOAD_UNAVAILABLE_MESSAGE) from exc

        value = None if is_zipped_state else str(zip_file_path)
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
        self._authorize_download(file_id, user_id)
        try:
            output_file_path = isolated_output_path(
                flowsettings.KH_ZIP_OUTPUT_DIR,
                file_id,
                ".html",
            )
        except ArtifactNamespaceError as exc:
            raise gr.Error(DOWNLOAD_UNAVAILABLE_MESSAGE) from exc
        with output_file_path.open("w", encoding="utf-8") as output_file:
            output_file.write(file_html)

        value = None if is_zipped_state else str(output_file_path)
        label = "Download" if is_zipped_state else DOWNLOAD_MESSAGE
        return not is_zipped_state, gr.DownloadButton(label=label, value=value)

    def _authorize_download(self, file_id, user_id) -> None:
        try:
            self._get_file_selection_service().source_name(file_id, user_id)
        except FileSelectionError as exc:
            raise gr.Error(DOWNLOAD_UNAVAILABLE_MESSAGE) from exc

    def _scoped_source_name(self, file_id, user_id) -> Path:
        try:
            return Path(
                self._get_file_selection_service().source_name(file_id, user_id)
            )
        except FileSelectionError as exc:
            raise gr.Error(str(exc)) from exc

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
