import inspect

from ktem.pages.chat import ChatPage, chat_layout


def test_chat_layout_helpers_own_workbench_construction_contract():
    source = inspect.getsource(chat_layout)
    layout_source = inspect.getsource(chat_layout.render_chat_workbench_layout)

    for helper_name in [
        "render_chat_workbench_layout",
        "render_workbench_states",
        "render_corpus_panel",
        "render_reader_panel",
        "render_answer_panel",
        "render_conversation_dock",
    ]:
        assert f"def {helper_name}" in source

    for elem_id in [
        'elem_id="page-workbench-layout"',
        'elem_id="conv-settings-panel"',
        'elem_id="reader-workbench"',
        'elem_id="chat-info-panel"',
        'elem_id="answer-expand"',
        'elem_id="conversation-dock"',
    ]:
        assert elem_id in source

    assert layout_source.index("render_corpus_panel(") < layout_source.index(
        "render_reader_panel("
    )
    assert layout_source.index("render_reader_panel(") < layout_source.index(
        "render_answer_panel("
    )


def test_chat_page_delegates_ui_construction_to_layout_helper():
    source = inspect.getsource(ChatPage.on_building_ui)

    assert "render_chat_workbench_layout(" in source
    assert len(source.splitlines()) <= 12


def test_chat_fn_stays_thin_gradio_callback_wrapper():
    source = inspect.getsource(ChatPage.chat_fn)

    assert "run_chat_callback_outputs(" in source
    assert len(source.splitlines()) <= 80
