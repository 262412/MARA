from __future__ import annotations

from typing import TypeAlias

import gradio as gr
from ktem.db.engine import engine

from .deletion import DeletionCoordinator, DeletionError
from ._identity import resolve_file_index_user_id

Request: TypeAlias = gr.Request | None


class FileIndexDeletionController:
    def __init__(self, index, selected_panel_false: str) -> None:
        self._index = index
        self._selected_panel_false = selected_panel_false

    def delete_event(self, file_id, user_id=None, request: Request = None):
        scoped_user_id = self._resolve_user_id(user_id, request)
        resources = self._index._resources
        coordinator = DeletionCoordinator(
            engine=engine,
            source_table=resources["Source"],
            index_table=resources["Index"],
            vector_store=resources["VectorStore"],
            doc_store=resources["DocStore"],
            file_storage_path=resources.get("FileStoragePath"),
        )
        try:
            result = coordinator.delete(file_id, user_id=scoped_user_id)
        except DeletionError as exc:
            raise gr.Error(str(exc)) from exc

        gr.Info(f"File {result.name} has been deleted")
        return None, self._selected_panel_false

    @staticmethod
    def _resolve_user_id(user_id, request: Request):
        return resolve_file_index_user_id(user_id, request)

    def delete_all_files(self, file_list, user_id=None, request: Request = None):
        for file_id in file_list.id.values:
            if not file_id or str(file_id) == "-":
                continue
            self.delete_event(file_id, user_id, request=request)

    @staticmethod
    def set_file_id_selector(selected_file_id):
        return [selected_file_id, "select", gr.Tabs(selected="chat-tab")]

    @staticmethod
    def show_delete_all_confirm(file_list):
        if len(file_list) == 0 or (
            len(file_list) == 1 and file_list.id.values[0] == "-"
        ):
            gr.Info("No file to delete")
            return [
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
            ]

        return [
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=True),
        ]
