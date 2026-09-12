"""Independent data preparation; old Web expectations live in characterization tests."""

import pytest
from ktem.docqa import chat_submission as core


def _inputs(**changes):
    values = dict(
        chat_input={"text": "Question", "files": []},
        chat_history=[],
        user_id="owner",
        settings={},
        first_selector_choices=[],
        graph_source_ids=[],
        selected_page_text="",
        default_question="Default",
        merge_graph_source_ids=lambda old, new: old + new,
        first_indexing_file_fn=None,
        first_indexing_url_fn=None,
    )
    return {**values, **changes}


def test_independent_core_keeps_history_completion_separate_from_source_preparation():
    choices = [("one.pdf", "one")]
    history = [["before", "answer"]]
    prepared = core.prepare_submission_content(
        **_inputs(
            chat_input={"text": 'Question @"one.pdf"'},
            first_selector_choices=choices,
            chat_history=history,
            selected_page_text=" selected\ntext ",
        )
    )
    assert (
        prepared.chat_input_text
        == "Question\n\n[Selected text from current page]\nselected text"
    )
    assert prepared.file_ids == ["one"]
    assert prepared.merged_graph_source_ids == ["one"]
    assert choices == [("one.pdf", "one")]
    assert history == [["before", "answer"]]
    completed = core.complete_chat_history(prepared.chat_input_text, history)
    assert completed == [["before", "answer"], (prepared.chat_input_text, None)]
    assert completed is not history and completed[0] is history[0]
    assert not hasattr(prepared, "selector_output")


def test_empty_core_result_has_a_typed_error_only_when_history_is_completed():
    prepared = core.prepare_submission_content(
        **_inputs(chat_input={"text": ""}, default_question="")
    )
    assert prepared.chat_input_text == ""
    assert prepared.file_ids == []
    with pytest.raises(core.EmptyChatError, match="^Empty chat$"):
        core.complete_chat_history(prepared.chat_input_text, [])
    history = [["earlier", "answer"]]
    assert core.complete_chat_history("", history) is history


def test_core_calls_explicit_index_operation_before_url_parsing_and_preserves_error():
    error = RuntimeError("index failed")
    calls = []

    def index_files(files, reindex, settings, user):
        calls.append((files, reindex, settings, user))
        raise error

    choices = [("old.pdf", "old")]
    inputs = _inputs(
        chat_input={"text": "https://example.test", "files": ["owned.pdf"]},
        first_selector_choices=choices,
        first_indexing_file_fn=index_files,
    )
    with pytest.raises(RuntimeError) as caught:
        core.prepare_submission_content(**inputs)
    assert caught.value is error
    assert calls == [(["owned.pdf"], True, inputs["settings"], "owner")]
    assert choices == [("old.pdf", "old")]
