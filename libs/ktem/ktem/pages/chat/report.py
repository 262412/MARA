from typing import Any, Optional

import gradio as gr
from ktem.app import BasePage
from ktem.auth.authorization import (
    CALLBACK_REQUEST,
    CallbackAuthorizationError,
    resolve_callback_user_id,
)
from ktem.db.models import Conversation, IssueReport, engine
from sqlalchemy import or_
from sqlmodel import Session, select


class ReportIssue(BasePage):
    def __init__(self, app, show_panel: Optional[bool] = None):
        self._app = app
        self._show_panel = show_panel
        self.on_building_ui()

    def on_building_ui(self):
        panel_visible = True if self._show_panel is None else bool(self._show_panel)
        with gr.Accordion(
            label="Feedback",
            open=False,
            elem_id="report-accordion",
            visible=panel_visible,
        ):
            self.correctness = gr.Radio(
                choices=[
                    ("The answer is correct", "correct"),
                    ("The answer is incorrect", "incorrect"),
                ],
                label="Correctness:",
            )
            self.issues = gr.CheckboxGroup(
                choices=[
                    ("The answer is offensive", "offensive"),
                    ("The evidence is incorrect", "wrong-evidence"),
                ],
                label="Other issue:",
            )
            self.more_detail = gr.Textbox(
                placeholder=(
                    "More detail (e.g. how wrong is it, what is the "
                    "correct answer, etc...)"
                ),
                container=False,
                lines=3,
            )
            gr.Markdown(
                "This will send the current chat and the user settings to "
                "help with investigation"
            )
            self.report_btn = gr.Button("Report")

    def report(
        self,
        correctness: str,
        issues: list[str],
        more_detail: str,
        conv_id: str,
        chat_history: list,
        settings: dict,
        user_id: Any,
        info_panel: str,
        chat_state: dict,
        request: gr.Request = CALLBACK_REQUEST,
        *selecteds,
    ):
        if not _is_request_value(request):
            selecteds = (request, *selecteds)
            request = CALLBACK_REQUEST
        principal = resolve_callback_user_id(user_id, request)
        normalized_conversation_id = str(conv_id or "").strip()
        if normalized_conversation_id:
            with Session(engine) as session:
                authorized_id = session.exec(
                    select(Conversation.id).where(
                        Conversation.id == normalized_conversation_id,
                        or_(
                            Conversation.user == principal,
                            Conversation.is_public.is_(True),
                        ),
                    )
                ).first()
            if authorized_id is None:
                raise CallbackAuthorizationError()

        selecteds_ = {}
        for index in self._app.index_manager.indices:
            if index.selector is not None:
                if isinstance(index.selector, int):
                    selecteds_[str(index.id)] = selecteds[index.selector]
                elif isinstance(index.selector, tuple):
                    selecteds_[str(index.id)] = [selecteds[_] for _ in index.selector]
                else:
                    print(f"Unknown selector type: {index.selector}")

        with Session(engine) as session:
            issue = IssueReport(
                issues={
                    "correctness": correctness,
                    "issues": issues,
                    "more_detail": more_detail,
                },
                chat={
                    "conv_id": conv_id,
                    "chat_history": chat_history,
                    "info_panel": info_panel,
                    "chat_state": chat_state,
                    "selecteds": selecteds_,
                },
                settings=settings,
                user=principal,
            )
            session.add(issue)
            session.commit()
        gr.Info("Thank you for your feedback")


def _is_request_value(value):
    return bool(
        value is CALLBACK_REQUEST
        or isinstance(value, gr.Request)
        or hasattr(value, "username")
        or hasattr(value, "session_hash")
    )
