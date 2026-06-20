from types import SimpleNamespace

from ktem.docqa._runtime_pipeline import (
    DEFAULT_SETTING,
    apply_request_setting_overrides,
)


def _default_request():
    return SimpleNamespace(
        llm=DEFAULT_SETTING,
        use_mindmap=DEFAULT_SETTING,
        use_citation=DEFAULT_SETTING,
        language=DEFAULT_SETTING,
        max_context_length=DEFAULT_SETTING,
    )


def test_runtime_adds_structured_markdown_guard_to_saved_qa_prompt():
    settings = {
        "reasoning.options.simple.qa_prompt": (
            "Use context to answer.\n{context}\nQuestion: {question}\nAnswer:"
        )
    }

    apply_request_setting_overrides(settings, "simple", _default_request())

    prompt = settings["reasoning.options.simple.qa_prompt"]
    assert "Return the final answer as Markdown" in prompt
    assert "Do not return one unbroken paragraph" in prompt
    assert "| Aspect | Summary |" in prompt
    assert "| --- | --- |" in prompt
    assert "never write pipe-delimited table rows inline" in prompt
    assert "Do not use backticks for mathematical variables" in prompt
    assert "triple backticks" in prompt


def test_runtime_does_not_duplicate_structured_markdown_guard():
    settings = {
        "reasoning.options.simple.qa_prompt": (
            "Return the final answer as Markdown.\n"
            "Use context to answer.\n{context}\nQuestion: {question}\nAnswer:"
        )
    }

    apply_request_setting_overrides(settings, "simple", _default_request())

    prompt = settings["reasoning.options.simple.qa_prompt"]
    assert prompt.count("Return the final answer as Markdown") == 1


def test_runtime_does_not_add_structured_guard_for_benchmark_origin():
    settings = {
        "reasoning.options.simple.qa_prompt": (
            "Use context to answer.\n{context}\nQuestion: {question}\nAnswer:"
        )
    }
    request = _default_request()
    request.origin = "benchmark"

    apply_request_setting_overrides(settings, "simple", request)

    prompt = settings["reasoning.options.simple.qa_prompt"]
    assert prompt == "Use context to answer.\n{context}\nQuestion: {question}\nAnswer:"
    assert "Answer formatting requirements:" not in prompt


def test_runtime_applies_request_max_context_length_override():
    settings = {
        "reasoning.options.simple.qa_prompt": (
            "Use context to answer.\n{context}\nQuestion: {question}\nAnswer:"
        ),
        "reasoning.max_context_length": 32000,
    }
    request = SimpleNamespace(
        llm=DEFAULT_SETTING,
        use_mindmap=DEFAULT_SETTING,
        use_citation=DEFAULT_SETTING,
        language=DEFAULT_SETTING,
        max_context_length=3000,
    )

    apply_request_setting_overrides(settings, "simple", request)

    assert settings["reasoning.max_context_length"] == 3000
