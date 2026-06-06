from kotaemon.indices.qa.citation_qa import AnswerWithContextPipeline
from kotaemon.indices.qa.citation_qa_inline import AnswerWithInlineCitation
from kotaemon.indices.qa.format_context import EVIDENCE_MODE_TEXT


def test_context_qa_prompt_requires_structured_markdown_tables_when_requested():
    pipeline = AnswerWithContextPipeline(
        citation_pipeline=lambda **kwargs: None,
        create_mindmap_pipeline=lambda **kwargs: None,
    )

    prompt, _ = pipeline.get_prompt(
        "请用表格总结这个文件讲了什么",
        "Transformers use attention to model token relationships.",
        EVIDENCE_MODE_TEXT,
    )

    assert "Return the final answer as Markdown" in prompt
    assert "Do not return one unbroken paragraph" in prompt
    assert "blank line between paragraphs" in prompt
    assert "If the user asks for a table" in prompt
    assert "| Aspect | Summary |" in prompt
    assert "| --- | --- |" in prompt
    assert "never write pipe-delimited table rows inline" in prompt
    assert "Do not use backticks for mathematical variables" in prompt
    assert "triple backticks" in prompt


def test_inline_citation_prompt_requires_same_structured_markdown_answer():
    pipeline = AnswerWithInlineCitation(
        citation_pipeline=lambda **kwargs: None,
        create_mindmap_pipeline=lambda **kwargs: None,
    )

    prompt, _ = pipeline.get_prompt(
        "summarize this document in a table",
        "The document covers attention, pretraining, and transformer blocks.",
        EVIDENCE_MODE_TEXT,
    )

    assert "Return the FINAL ANSWER as Markdown" in prompt
    assert "Do not return one unbroken paragraph" in prompt
    assert "If the user asks for a table" in prompt
    assert "| Aspect | Summary |" in prompt
    assert "| --- | --- |" in prompt
    assert "never write pipe-delimited table rows inline" in prompt
    assert "Do not use backticks for mathematical variables" in prompt
    assert "triple backticks" in prompt
