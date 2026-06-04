from __future__ import annotations

import gradio as gr
from ktem.db.engine import engine
from sqlalchemy import select
from sqlalchemy.orm import Session

from .element_index import is_docstore_relation_type


class FileIndexDeletionController:
    def __init__(self, index, selected_panel_false: str) -> None:
        self._index = index
        self._selected_panel_false = selected_panel_false

    def delete_event(self, file_id):
        file_name = ""
        with Session(engine) as session:
            source = session.execute(
                select(self._index._resources["Source"]).where(
                    self._index._resources["Source"].id == file_id
                )
            ).first()
            if source:
                file_name = source[0].name
                session.delete(source[0])

            vs_ids: list[str] = []
            ds_ids: list[str] = []
            index_rows = session.execute(
                select(self._index._resources["Index"]).where(
                    self._index._resources["Index"].source_id == file_id
                )
            ).all()
            for each in index_rows:
                if each[0].relation_type == "vector":
                    vs_ids.append(each[0].target_id)
                elif is_docstore_relation_type(each[0].relation_type):
                    ds_ids.append(each[0].target_id)
                session.delete(each[0])
            session.commit()

        if vs_ids:
            self._index._vs.delete(vs_ids)
        if ds_ids:
            self._index._docstore.delete(ds_ids)

        gr.Info(f"File {file_name} has been deleted")
        return None, self._selected_panel_false

    def delete_all_files(self, file_list):
        for file_id in file_list.id.values:
            if not file_id or str(file_id) == "-":
                continue
            self.delete_event(file_id)

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
