"""The real cold parent must not pull Web or runtime services into preparation."""

from ktem_tests.docqa_import_test_helpers import run_docqa_import_probe


def test_submission_import_and_independent_calls_have_no_runtime_side_effects():
    result = run_docqa_import_probe(
        r"""
from ktem.docqa import chat_submission
assert Path(chat_submission.__file__).parent == Path(ktem.__file__).parent / 'docqa'
calls = []
choices = [('old.pdf', 'old')]
history = [('earlier', 'answer')]
def files(values, reindex, settings, user):
    calls.append(('files', values, reindex, settings, user))
    return [' new ', 'new']
def urls(values, reindex, settings, user, request):
    assert request is None
    calls.append(('urls', values, reindex, settings, user))
    return ['url']
prepared = chat_submission.prepare_submission_content(
    chat_input={'text': 'Ask @"web" https://example.test', 'files': ['a.pdf', 'b.pdf']},
    chat_history=history, user_id='owner', settings={'key': 1},
    first_selector_choices=choices, graph_source_ids=['old'], selected_page_text=' page\n text ',
    default_question='Default', merge_graph_source_ids=lambda old, new: old + new,
    first_indexing_file_fn=files, first_indexing_url_fn=urls,
)
assert prepared.chat_input_text == 'Ask\n\n[Selected text from current page]\npage text'
assert prepared.file_ids == ['new', 'url']
assert prepared.merged_graph_source_ids == ['old', 'new', 'url']
assert prepared.used_command == 'web'
assert choices == [('old.pdf', 'old'), ('a.pdf', ' new '), ('b.pdf', 'new'), ('https://example.test', 'url')]
assert [item[0] for item in calls] == ['files', 'urls']
assert history == [('earlier', 'answer')]
assert chat_submission.complete_chat_history(prepared.chat_input_text, history)[-1] == (prepared.chat_input_text, None)
"""
    )
    blocked = (
        "ktem.pages",
        "ktem.docqa.runtime",
        "ktem.docqa._runtime_session_service",
        "ktem.db",
        "ktem.index",
        "ktem.llms",
        "ktem.embeddings",
        "ktem.rerankings",
        "ktem.components",
        "gradio",
        "sqlmodel",
        "sqlalchemy",
        "llama_index",
        "torch",
    )
    assert not any(
        name == prefix or name.startswith(prefix + ".")
        for name in result["added_modules"]
        for prefix in blocked
    ), result
    assert result["added_events"] == []
