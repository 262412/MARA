"""The real conversation tail restores authorized Studio records after refresh."""

from types import SimpleNamespace

import pytest
from gradio.helpers import special_args
from ktem.db.models import Conversation, engine
from ktem.docqa import _runtime_notebook as notebook
from ktem.pages.chat.chat_conversation_events import bind_chat_conversation_events
from ktem_tests.event_chain_spy import EventGraphSpy, build_chat_page, linear_chain
from sqlmodel import Session


@pytest.mark.parametrize(
    "public,viewer,visible",
    [(False, "owner", True), (True, "reader", True), (False, "reader", False)],
)
def test_conversation_tail_uses_authenticated_notebook_and_keeps_old_renderer(
    public, viewer, visible
):
    row = Conversation(user="owner", is_public=public)
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        conversation_id = row.id
    notebook.save_artifact_to_conversation(
        conversation_id,
        user_id="owner",
        artifact_type="study_guide",
        title="Owned saved guide",
        payload={"summary": "Owned evidence"},
    )
    try:
        graph = EventGraphSpy()
        page = build_chat_page(graph)
        calls = []
        history, retrieval = [["question", "answer"]], ["citation"]
        request = SimpleNamespace(username=viewer, session_hash="restored")

        def render(actual_history, actual_retrieval):
            assert actual_history is history and actual_retrieval is retrieval
            calls.append("legacy renderer")
            return "legacy empty Studio"

        def identity(user_id, actual):
            assert user_id == "forged" and actual is request
            calls.append("identity")
            return viewer

        page.render_latest_reasoning_trace = render
        page._resolve_persist_user_id = identity
        bind_chat_conversation_events(
            page,
            demo_mode=False,
            chat_input_focus_js="focus",
            clear_bot_message_selection_js="clear",
            pdfview_js="pdf",
        )
        chain = linear_chain(graph, graph.roots("chat_control.conversation")[0])
        event = next(
            call.params
            for call in chain
            if call.params.get("outputs") == [page.reasoning_trace_panel]
        )
        assert event["inputs"] == [
            page.chat_panel.chatbot,
            page.state_retrieval_history,
            page.chat_control.conversation_id,
            page._app.user_id,
        ]
        args, _, _ = special_args(
            event["fn"],
            inputs=[history, retrieval, conversation_id, "forged"],
            request=request,
        )
        result = event["fn"](*args)
        assert ("Owned saved guide" in result) is visible
        if not visible:
            assert result == "legacy empty Studio"
        assert calls == ["identity", "legacy renderer"]
    finally:
        with Session(engine) as session:
            session.delete(session.get(Conversation, conversation_id))
            session.commit()
