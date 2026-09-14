from __future__ import annotations

import json
from copy import copy
from threading import Lock
from typing import TypeAlias

import gradio as gr
from ktem.app import BasePage
from ktem.db.engine import engine
from sqlalchemy import select
from sqlalchemy.orm import Session
from theflow.settings import settings as flowsettings

from ...utils.commands import WEB_SEARCH_COMMAND
from ._identity import MISSING_REQUEST, resolve_file_index_user_id

MAX_FILE_COUNT = 200
Request: TypeAlias = gr.Request

UPDATE_FILE_LIST_JS = """
function(file_list) {
    var values = [];
    for (var i = 0; i < file_list.length; i++) {
        values.push({
            key: file_list[i][0],
            value: '"' + file_list[i][0] + '"',
        });
    }

    values.push({
        key: "web_search",
        value: '"web_search"',
    });

    var tribute = new Tribute({
        values: values,
        noMatchTemplate: "",
        allowSpaces: true,
    })
    input_box = document.querySelector('#chat-input textarea');
    tribute.detach(input_box);
    tribute.attach(input_box);
}
""".replace(
    "web_search", WEB_SEARCH_COMMAND
)


class FileSelector(BasePage):
    """File selector UI in the Chat page."""

    def __init__(self, app, index):
        super().__init__(app)
        self._index = index
        self._choices_lock = Lock()
        self.on_building_ui()

    def default(self):
        if self._app.f_user_management:
            return "disabled", [], -1
        return "disabled", [], 1

    def on_building_ui(self):
        default_mode, default_selector, user_id = self.default()
        self.mode = gr.Radio(
            value=default_mode,
            choices=[("Search All", "all"), ("Search In File(s)", "select")],
            container=False,
        )
        self.selector = gr.Dropdown(
            label="Files",
            value=default_selector,
            choices=[],
            multiselect=True,
            container=False,
            interactive=True,
            visible=False,
        )
        self.selector_user_id = gr.State(value=user_id)
        self.selector_choices = gr.JSON(value=[], visible=False)
        self._files_result = gr.JSON(value=None, visible=False)
        self._files_stamp = gr.JSON(value=None, visible=False)
        self._files_applied = gr.State(value={})

    def on_register_events(self):
        from ktem.pages.chat.file_browser_updates import APPLY_SELECTOR_JS

        self._files_result.change(
            fn=None,
            inputs=[self._files_result, self.selector],
            outputs=[self.selector, self.selector_choices],
            js=APPLY_SELECTOR_JS,
            show_progress="hidden",
        )
        self.mode.change(
            fn=self.mode_changed,
            inputs=[self.mode, self._app.user_id],
            outputs=[self.selector, self.selector_user_id],
        )
        if self._index.id == 1:
            self.selector_choices.change(
                fn=None,
                inputs=[self.selector_choices],
                js=UPDATE_FILE_LIST_JS,
                show_progress="hidden",
            )

    def as_gradio_component(self):
        return [self.mode, self.selector, self.selector_user_id]

    def mode_changed(
        self,
        mode,
        user_id,
        request: Request = MISSING_REQUEST,
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        return gr.update(visible=mode == "select"), user_id

    def get_selected_ids(self, components):
        mode, selected, user_id = components[0], components[1], components[2]
        if user_id is None or mode == "disabled":
            return []
        if mode == "select":
            return selected

        source_table = self._index._resources["Source"]
        statement = select(source_table.id)
        if self._index.config.get("private", False) or getattr(
            self._app, "f_user_management", False
        ):
            statement = statement.where(source_table.user == user_id)
        with Session(engine) as session:
            return [file_id for (file_id,) in session.execute(statement).all()]

    def load_files(
        self,
        selected_files,
        user_id,
        request: Request = MISSING_REQUEST,
    ):
        user_id = resolve_file_index_user_id(user_id, request)
        options: list = []
        available_ids: list[str] = []
        if user_id is None:
            return gr.update(value=selected_files, choices=options), options

        with Session(engine) as session:
            statement = select(self._index._resources["Source"])
            if self._index.config.get("private", False) or getattr(
                self._app, "f_user_management", False
            ):
                statement = statement.where(
                    self._index._resources["Source"].user == user_id
                )
            if getattr(flowsettings, "KH_DEMO_MODE", False):
                statement = statement.limit(MAX_FILE_COUNT)
            for (source,) in session.execute(statement).all():
                available_ids.append(source.id)
                options.append((source.name, source.id))

            group_table = self._index._resources["FileGroup"]
            statement = select(group_table).where(group_table.user == user_id)
            for (group,) in session.execute(statement).all():
                options.append(
                    (f"group: '{group.name}'", json.dumps(group.data.get("files", [])))
                )

        if selected_files:
            available_ids_set = set(available_ids)
            selected_files = [
                file_id for file_id in selected_files if file_id in available_ids_set
            ]
        return gr.update(value=selected_files, choices=options), options

    def _on_app_created(self):
        self._app.app.load(**self._load_files_event())

    def on_subscribe_public_events(self):
        self._app.subscribe_event(
            name=f"onFileIndex{self._index.id}Changed",
            definition=self._load_files_event(index_changed=True),
        )
        if self._app.f_user_management:
            for event_name in ["onSignIn", "onSignOut"]:
                self._app.subscribe_event(
                    name=event_name,
                    definition=self._load_files_event(),
                )

    def _load_files_event(self, *, index_changed=False):
        from ktem.pages.chat.file_browser_updates import (
            CAPTURE_SELECTOR_JS,
            file_selector_result,
        )

        return {
            "fn": file_selector_result(self.load_files, self._apply_file_choices),
            "inputs": [
                self.selector,
                self._app.user_id,
                self._files_stamp,
                self._files_applied,
            ],
            "outputs": [self._files_result],
            "js": CAPTURE_SELECTOR_JS.replace("INDEX_ID", str(self._index.id)).replace(
                "INDEX_CHANGED", "true" if index_changed else "false"
            ),
            "show_progress": "hidden",
        }

    def _apply_file_choices(self, stamp, options, applied):
        """Keep Gradio's per-session component vocabulary in delivery order.

        The final browser gate owns the visible options. Gradio 4.39 also keeps
        component constructor arguments on the server for subsequent updates;
        a JavaScript-only output cannot update that session-local vocabulary.
        The lock covers only the copy/assignment, never the authorized query.
        """
        from gradio.context import LocalContext

        config = LocalContext.blocks_config.get()
        if config is None:
            raise RuntimeError("File choices require an active Gradio session")
        with self._choices_lock:
            if (
                applied.get("epoch") == stamp["epoch"]
                and applied.get("selectorRequest", 0) > stamp["selectorRequest"]
            ):
                return
            component = copy(config.blocks[self.selector._id])
            component.choices = list(options)
            component._constructor_args = [
                dict(component.constructor_args, choices=list(options)),
                *component._constructor_args[1:],
            ]
            config.blocks[self.selector._id] = component
            applied.update(stamp)


__all__ = ["FileSelector"]
