from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path
from typing import Any, TypeAlias

import gradio as gr
from theflow.settings import settings as flowsettings

from kotaemon.artifact_downloads import DownloadWorkspace
from kotaemon.artifact_manifest import close_manifest_artifacts
from kotaemon.artifact_namespace import ArtifactNamespaceError, load_manifest_artifacts

from ._group_service import GroupServiceError
from ._identity import MISSING_REQUEST, resolve_file_index_user_id
from ._selection_service import FileSelectionError
from .download_scope import DownloadScope

DOWNLOAD_MESSAGE = "Start download"
DOWNLOAD_UNAVAILABLE_MESSAGE = (
    "File export is unavailable; reindex the file and try again."
)
Request: TypeAlias = gr.Request
logger = logging.getLogger(__name__)


def _cleanup_workspace(workspace: DownloadWorkspace) -> None:
    try:
        workspace.cleanup()
    except Exception:
        logger.exception("Failed to clean up isolated download workspace")


class ScopedFileIndexPageMixin:
    _listing_controller: Any
    _index: Any

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
        if is_zipped_state:
            return False, gr.DownloadButton(label="Download", value=None)
        scope = self._download_scope(file_id, user_id, request)
        artifacts = []
        workspace = None
        try:
            artifacts = load_manifest_artifacts(
                file_id,
                {
                    "chunks": flowsettings.KH_CHUNKS_OUTPUT_DIR,
                    "markdown": flowsettings.KH_MARKDOWN_OUTPUT_DIR,
                },
                flowsettings.KH_ZIP_OUTPUT_DIR,
            )
            workspace = DownloadWorkspace.create(
                flowsettings.KH_ZIP_OUTPUT_DIR,
                file_id,
                ".zip",
            )
            with workspace.open_temporary() as output:
                with zipfile.ZipFile(output, "w") as archive:
                    for artifact in artifacts:
                        with archive.open(artifact.archive_name, "w") as target:
                            artifact.copy_to(target)
                output.flush()
                os.fsync(output.fileno())
            zip_file_path = self._publish_download(workspace, scope)
        except (
            ArtifactNamespaceError,
            OSError,
            RuntimeError,
            ValueError,
            zipfile.BadZipFile,
            zipfile.LargeZipFile,
        ) as exc:
            if workspace is not None:
                _cleanup_workspace(workspace)
            raise gr.Error(DOWNLOAD_UNAVAILABLE_MESSAGE) from exc
        except BaseException:
            if workspace is not None:
                _cleanup_workspace(workspace)
            raise
        finally:
            close_manifest_artifacts(artifacts)

        return True, self._download_button(zip_file_path, file_id, request)

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
        if is_zipped_state:
            return False, gr.DownloadButton(label="Download", value=None)
        scope = self._download_scope(file_id, user_id, request)
        workspace = None
        try:
            workspace = DownloadWorkspace.create(
                flowsettings.KH_ZIP_OUTPUT_DIR,
                file_id,
                ".html",
            )
            with workspace.open_temporary() as output_file:
                output_file.write(str(file_html).encode("utf-8"))
                output_file.flush()
                os.fsync(output_file.fileno())
            output_file_path = self._publish_download(workspace, scope)
        except (ArtifactNamespaceError, OSError, TypeError, ValueError) as exc:
            if workspace is not None:
                _cleanup_workspace(workspace)
            raise gr.Error(DOWNLOAD_UNAVAILABLE_MESSAGE) from exc
        except BaseException:
            if workspace is not None:
                _cleanup_workspace(workspace)
            raise

        return True, self._download_button(output_file_path, file_id, request)

    def _download_scope(self, file_id, user_id, request):
        if request is MISSING_REQUEST or request is None:
            # Preserve trusted direct-call file results. Remote callbacks always
            # receive Gradio's injected Request and use the scoped HTTP path.
            return None
        try:
            return DownloadScope(self._get_file_selection_service(), file_id, user_id)
        except FileSelectionError as exc:
            raise gr.Error(DOWNLOAD_UNAVAILABLE_MESSAGE) from exc

    @staticmethod
    def _publish_download(workspace, scope):
        if scope is None:
            return workspace.publish()
        with scope.current():
            return workspace.publish(context=scope.context)

    def _download_button(self, path, file_id, request):
        if request is MISSING_REQUEST or request is None:
            return gr.DownloadButton(label=DOWNLOAD_MESSAGE, value=str(path))
        from .download_http import download_button

        return download_button(path, self._index.id, file_id, request)

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
