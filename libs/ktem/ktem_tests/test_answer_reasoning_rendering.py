from typing import Any, cast

from ktem.pages.chat import ChatPage
from ktem.pages.chat.answer_reasoning import render_answer_reasoning_block


def test_streaming_reasoning_block_uses_open_shimmer_status():
    html = render_answer_reasoning_block(is_streaming=True)

    assert "answer-reasoning-block" in html
    assert "answer-reasoning-block--streaming" in html
    assert "open" in html
    assert "aria-busy='true'" in html
    assert "answer-reasoning-shimmer" in html
    assert "Thinking" in html
    assert "chain-of-thought" not in html.lower()


def test_streaming_reasoning_block_reflects_live_events():
    html = render_answer_reasoning_block(
        is_streaming=True,
        stream_events=[
            {
                "channel": "debug",
                "content": {
                    "mara_channel": "agent_trace",
                    "payload": {"event": "route"},
                },
            },
            {
                "channel": "debug",
                "content": {
                    "mara_channel": "evidence_metadata",
                    "payload": {"modalities": {"text": 1}},
                },
            },
            {"channel": "chat", "content": "partial answer"},
        ],
    )

    assert "3 live events" in html
    assert "Retrieval metadata received" in html
    assert "Streaming answer text" in html
    assert "is-done" in html
    assert "is-active" in html


def test_completed_reasoning_block_is_collapsed_controller_summary():
    html = render_answer_reasoning_block(
        route_decision={"route": "doc_text"},
        retrieve_decision={"status": "good"},
        verify_decision={"status": "supported", "action": "generate"},
        evidence_bundle={"items": [{"modality": "text"}, {"modality": "page_image"}]},
    )

    assert "<details class='answer-reasoning-block'>" in html
    assert "aria-busy='false'" in html
    assert "Reasoning" in html
    assert "Text evidence" in html
    assert "Page image evidence" in html
    assert "supported" in html
    assert "2 evidence items" in html
    assert "raw" not in html.lower()


def test_completed_reasoning_block_omits_empty_trace():
    assert render_answer_reasoning_block() == ""


def test_answer_panel_places_reasoning_inside_current_exchange():
    page = cast(Any, ChatPage.__new__(ChatPage))

    html = page._generate_answer_panel_html(
        [],
        "What changed?",
        "The answer.",
        reasoning_html="<details class='answer-reasoning-block'></details>",
    )

    question_index = html.index("What changed?")
    reasoning_index = html.index("answer-reasoning-block")
    answer_index = html.index("The answer.")
    assert question_index < reasoning_index < answer_index
