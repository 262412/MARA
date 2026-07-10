from types import SimpleNamespace

from ktem.pages.chat.chat_conversation_events import _bind_demo_conversation_events


class _Chain:
    def then(self, *args, **kwargs):
        return self


class _Button:
    def __init__(self):
        self.calls = []

    def click(self, *args, **kwargs):
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

    _bind_demo_conversation_events(page, "focus")

    assert btn_new.calls[0][1]["fn"] is clear_conv
