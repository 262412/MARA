from ktem.pages.chat.chat_submission import SELECTION_MARKER, prepare_chat_submission


def test_prepare_chat_submission_preserves_indexing_selection_and_graph_scope():
    indexed_calls = []

    def index_files(files, reindex, settings, user_id):
        indexed_calls.append((files, reindex, settings, user_id))
        return ["file-1"]

    def merge_graph_source_ids(current_ids, new_ids):
        merged = []
        for file_id in [*current_ids, *new_ids]:
            if file_id not in merged:
                merged.append(file_id)
        return merged

    result = prepare_chat_submission(
        chat_input={"text": "Summarize this document", "files": ["/tmp/alpha.pdf"]},
        chat_history=[],
        user_id=1,
        settings={"reasoning.use": "mara"},
        first_selector_choices=[],
        graph_source_ids=["file-9"],
        selected_page_text="Selected page evidence.",
        selected_graph_context='{"related_file_ids": ["file-9"]}',
        default_question="What is the summary of this document?",
        merge_graph_source_ids=merge_graph_source_ids,
        first_indexing_file_fn=index_files,
        first_indexing_url_fn=None,
    )

    expected_question = (
        "Summarize this document\n\n" f"{SELECTION_MARKER}\n" "Selected page evidence."
    )
    assert indexed_calls == [(["/tmp/alpha.pdf"], True, {"reasoning.use": "mara"}, 1)]
    assert result.chat_input_text == expected_question
    assert result.chat_history == [(expected_question, None)]
    assert result.selector_output[0] == "select"
    assert result.selector_output[1]["value"] == ["file-1"]
    assert result.selector_output[1]["choices"] == [("alpha.pdf", "file-1")]
    assert result.selected_page_text == "Selected page evidence."
    assert result.selected_graph_context == '{"related_file_ids": ["file-9"]}'
    assert result.merged_graph_source_ids == ["file-9", "file-1"]
