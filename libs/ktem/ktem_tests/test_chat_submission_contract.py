"""Fixed submission values, identities, failures and source precedence."""

from dataclasses import fields
from types import SimpleNamespace
from typing import Any

import gradio as gr
import pytest
from ktem.pages.chat import chat_submission as submission
from ktem.pages.chat import chat_submit_sources as sources

from .chat_submission_test_helpers import FULL_TRACE, SubmissionProbe


@pytest.fixture
def probe(monkeypatch):
    return SubmissionProbe(monkeypatch)


def test_ordered_submission_values_and_original_type(probe):
    result = probe.prepare()
    question = "Ask\n\n[Selected text from current page]\nSelected evidence"
    assert probe.names == FULL_TRACE
    assert type(result) is submission.PreparedChatSubmission
    assert type(result).__module__ == "ktem.pages.chat.chat_submission"
    assert [field.name for field in fields(result)] == [
        "chat_input_text",
        "chat_history",
        "selector_output",
        "used_command",
        "selected_page_text",
        "selected_graph_context",
        "merged_graph_source_ids",
    ]
    assert result.chat_input_text == question
    assert result.chat_history == [["old question", "old answer"], (question, None)]
    assert result.chat_history is not probe.history
    assert result.chat_history[0] is probe.history[0]
    assert probe.history == [["old question", "old answer"]]
    assert result.selector_output == [
        "select",
        {
            "value": ["upload-id", "url-id"],
            "choices": [
                ("named.pdf", "named-id"),
                ("upload.pdf", "upload-id"),
                ("https://example.test/a", "url-id"),
            ],
            "__type__": "update",
        },
    ]
    assert result.selector_output[1]["choices"] is probe.choices
    assert result.selected_graph_context is probe.context
    assert result.merged_graph_source_ids is probe.graph_result
    assert result.used_command is None
    assert probe.call("index_files")[1] == (
        ["/owned/upload.pdf"],
        True,
        probe.settings,
        "owner",
    )
    assert probe.call("index_urls")[1] == (
        "https://example.test/a",
        True,
        probe.settings,
        "owner",
    )
    assert probe.call("index_urls")[2] == {"request": None}
    assert probe.call("index_files")[1][2] is probe.settings


@pytest.mark.parametrize("stage", FULL_TRACE)
def test_failures_keep_exact_prefix_identity_and_prior_mutation(probe, stage):
    probe.fail_at = stage
    with pytest.raises(RuntimeError) as caught:
        probe.prepare()
    assert caught.value is probe.failure
    assert probe.names == FULL_TRACE[: FULL_TRACE.index(stage) + 1]
    expected = [("named.pdf", "named-id")]
    if FULL_TRACE.index(stage) > FULL_TRACE.index("extend_choices"):
        expected += [("upload.pdf", "upload-id"), ("https://example.test/a", "url-id")]
    assert probe.choices == expected
    assert probe.history == [["old question", "old answer"]]


@pytest.mark.parametrize("value", [None, {}])
def test_empty_input_fails_before_any_boundary(probe, value):
    with pytest.raises(ValueError, match="^Input is empty$"):
        probe.prepare(chat_input=value)
    assert probe.names == []


@pytest.mark.parametrize(
    "history,text,selection,default,expected",
    [
        ([], "", "", "Default", "Default"),
        ([], "   ", "", "Default", "Default"),
        ([], "  Text  ", "", "Default", "Text"),
        ([["q", "a"]], "", "", "Default", ""),
        (
            [["q", "a"]],
            "",
            "  Selected\n text ",
            "Default",
            "Please explain the following selected text from the current page:\nSelected text",
        ),
        (
            [],
            "",
            " Select ",
            "Default",
            "Default\n\n[Selected text from current page]\nSelect",
        ),
        (
            [],
            "[Selected text from current page]\nExisting",
            " New  text ",
            "Default",
            "[Selected text from current page]\nExisting",
        ),
    ],
)
def test_text_default_history_and_selection_fixed_values(
    probe,
    history,
    text,
    selection,
    default,
    expected,
):
    result = probe.prepare(
        chat_input={"text": text},
        chat_history=history,
        selected_page_text=selection,
        default_question=default,
    )
    assert result.chat_input_text == expected
    assert result.chat_history == history + ([(expected, None)] if expected else [])
    assert (result.chat_history is history) == (not expected)
    assert result.selector_output == [{"__type__": "update"}, {"__type__": "update"}]
    assert result.selected_page_text == (
        " ".join(selection.split()) if selection.strip() else selection
    )


def test_empty_chat_error_occurs_after_selector_updates(probe):
    with pytest.raises(gr.Error) as caught:
        probe.prepare(
            chat_input={"text": ""},
            chat_history=[],
            selected_page_text="",
            default_question="",
        )
    assert caught.value.message == "Empty chat"
    assert probe.names == [
        "sources",
        "file_names",
        "urls",
        "merge_files",
        "extend_choices",
        "merge_graph",
        "selection",
        "update",
        "update",
    ]


@pytest.mark.parametrize(
    "url_callback,expected", [(True, ["url-id"]), (False, ["named-id"])]
)
def test_url_branch_takes_precedence_only_when_indexer_exists(
    probe, url_callback, expected
):
    result = probe.prepare(
        chat_input={"text": '@"named.pdf" https://example.test/a'},
        first_indexing_url_fn=probe.index_urls if url_callback else None,
    )
    assert result.selector_output[1]["value"] == expected
    assert probe.names.count("index_urls") == int(url_callback)


def test_missing_file_indexer_ignores_upload_and_keeps_no_update(probe):
    result = probe.prepare(
        chat_input={"files": ["/owned/upload.pdf"]},
        first_indexing_file_fn=None,
        selected_page_text="",
    )
    assert "index_files" not in probe.names
    assert result.chat_history is probe.history
    assert result.selector_output == [{"__type__": "update"}, {"__type__": "update"}]


def test_files_only_use_default_even_with_existing_history(probe):
    result = probe.prepare(
        chat_input={"files": ["/owned/upload.pdf"]}, selected_page_text=""
    )
    assert result.chat_input_text == "Default question"
    assert result.chat_history[-1] == ("Default question", None)


def test_web_search_keeps_command_with_url_and_file_inputs(probe):
    result = probe.prepare(
        chat_input={
            "text": f'@"{sources.WEB_SEARCH_COMMAND}" @"named.pdf" https://example.test/a'
        }
    )
    assert result.used_command == sources.WEB_SEARCH_COMMAND
    assert result.selector_output[1]["value"] == ["url-id"]


def test_choice_map_precedes_indexing_mutation(probe):
    def index_files(*args):
        probe.choices.append(("later.pdf", "late-id"))
        return ["upload-id"]

    result = probe.prepare(
        chat_input={"text": '@"later.pdf"', "files": ["x"]},
        first_indexing_file_fn=index_files,
    )
    assert result.selector_output[1]["value"] == ["upload-id"]
    assert ("later.pdf", "late-id") in probe.choices


def test_global_parser_patch_is_resolved_after_indexing(probe, monkeypatch):
    def index_files(*args):
        monkeypatch.setattr(sources, "get_urls", lambda text: ([], "Patched text"))
        monkeypatch.setattr(
            submission,
            "_inject_selected_page_text",
            lambda text, selected: (text + "!", selected),
        )
        return ["upload-id"]

    result = probe.prepare(first_indexing_file_fn=index_files)
    assert result.chat_input_text == "Patched text!"
    assert result.selector_output[1]["value"] == ["upload-id", "named-id"]
    assert "index_urls" not in probe.names and "selection" not in probe.names


@pytest.mark.parametrize("context", [None, "", "invalid-json", [], {"node": [1]}])
def test_graph_context_is_not_parsed_or_copied(probe, context):
    assert (
        probe.prepare(selected_graph_context=context).selected_graph_context is context
    )


def test_original_empty_choices_and_invalid_text_fail_at_original_stage(probe):
    with pytest.raises(AttributeError):
        probe.prepare(first_selector_choices=None)
    assert probe.names == FULL_TRACE[:7]
    probe.calls.clear()
    with pytest.raises(TypeError):
        probe.prepare(chat_input={"text": None, "files": ["x"]})
    assert probe.names == FULL_TRACE[:4]


def test_uploaded_names_and_id_normalization_fixed_values():
    assert sources._chat_uploaded_file_names(
        [
            {"orig_name": "original.pdf", "name": "other.pdf", "path": "path.pdf"},
            {"name": "name.pdf", "path": "path.pdf"},
            {"path": "path.pdf"},
            SimpleNamespace(orig_name="attribute.pdf", name="ignored.pdf"),
            SimpleNamespace(name="attribute-name.pdf"),
            "plain.pdf",
            {},
            None,
        ]
    ) == [
        "original.pdf",
        "name.pdf",
        "path.pdf",
        "attribute.pdf",
        "attribute-name.pdf",
        "plain.pdf",
        "",
        "",
    ]
    mixed_ids: list[Any] = [" a ", "a", "", None, 0, False, "b", 2]
    assert sources._merge_unique_file_ids(mixed_ids) == [
        "a",
        "b",
        "2",
    ]
