from types import SimpleNamespace
from typing import cast

from ktem.pages.chat.chat_auxiliary_events import (
    _bind_user_feedback_events,
    bind_chat_pre_studio_events,
)
from ktem.pages.chat.chat_conversation_events import _bind_demo_conversation_events
from ktem.pages.chat.chat_gradio_adapters import ChatConversationPorts


class _Chain:
    def then(self, *args, **kwargs):
        return self

    def success(self, *args, **kwargs):
        return self


class _Button:
    def __init__(self):
        self.calls = []

    def click(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _Chain()

    def change(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _Chain()

    def like(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _Chain()


def test_demo_new_chat_binds_clear_conversation_callback():
    btn_new = _Button()
    btn_logout = _Button()
    clear_conv = object()
    page = SimpleNamespace(
        chat_control=SimpleNamespace(
            btn_demo_logout=btn_logout,
            btn_new=btn_new,
            clear_conv=clear_conv,
            logout_js="logout",
            conversation_id=object(),
            conversation=object(),
            conversation_rn=object(),
            cb_is_public=object(),
        ),
        chat_panel=SimpleNamespace(chatbot=object()),
        followup_questions=object(),
        info_panel=object(),
        state_plot_panel=object(),
        state_retrieval_history=object(),
        state_plot_history=object(),
        state_chat=object(),
        _indices_input=[],
        paper_list=SimpleNamespace(accordion=object()),
        chat_settings=object(),
        answer_panel=object(),
        citations_panel=object(),
        reasoning_trace_panel=object(),
        _last_question=object(),
        _app=SimpleNamespace(settings_state=object()),
        language=object(),
        _use_suggestion=object(),
        followup_questions_ui=object(),
        render_latest_citations_card=object(),
        render_latest_reasoning_trace=object(),
        suggest_chat_conv=object(),
    )

    def port(*, inputs=None, outputs=None):
        return SimpleNamespace(gradio_inputs=inputs, gradio_outputs=outputs)

    ports = SimpleNamespace(
        selection=port(outputs=[]),
        demo_visibility=port(outputs=[]),
        clear_answer=port(outputs=[]),
        citations=port(inputs=[], outputs=[]),
        reasoning=port(inputs=[], outputs=[]),
        last_question=port(outputs=[]),
        suggestions=port(inputs=[], outputs=[]),
    )

    _bind_demo_conversation_events(
        page,
        cast(ChatConversationPorts, ports),
        "focus",
    )

    assert btn_new.calls[0][1]["fn"] is clear_conv


def test_public_and_like_events_include_local_user_identity():
    cb_is_public = _Button()
    cb_suggest_chat = _Button()
    reasoning_type = _Button()
    chatbot = _Button()
    report_btn = _Button()
    app = SimpleNamespace(user_id="user-id", settings_state="settings")
    page = SimpleNamespace(
        _app=app,
        _indices_input=[],
        _reasoning_type="reasoning-state",
        _use_suggestion="suggestion-state",
        followup_questions_ui="suggestion-ui",
        reasoning_type=reasoning_type,
        reasoning_changed=object(),
        on_set_public_conversation=object(),
        is_liked=object(),
        info_panel="info",
        state_chat="chat-state",
        chat_panel=SimpleNamespace(chatbot=chatbot),
        chat_control=SimpleNamespace(
            cb_is_public=cb_is_public,
            cb_suggest_chat=cb_suggest_chat,
            conversation="conversation",
            conversation_id="conversation-id",
        ),
        report_issue=SimpleNamespace(
            report_btn=report_btn,
            report=object(),
            correctness="correctness",
            issues="issues",
            more_detail="detail",
        ),
    )

    bind_chat_pre_studio_events(
        page,
        demo_mode=True,
        on_suggest_chat_event={},
        pdfview_js="",
    )
    _bind_user_feedback_events(page)

    assert cb_is_public.calls[0][1]["inputs"] == [
        cb_is_public,
        "conversation",
        "user-id",
    ]
    assert chatbot.calls[0][1]["inputs"] == ["conversation-id", "user-id"]
    assert report_btn.calls[-1][1]["inputs"] == [
        "correctness",
        "issues",
        "detail",
        "conversation-id",
        chatbot,
        "settings",
        "user-id",
        "info",
        "chat-state",
    ]
