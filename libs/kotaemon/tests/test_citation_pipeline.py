from types import SimpleNamespace

from kotaemon.indices.qa.citation import CitationPipeline


def test_citation_pipeline_disables_deepseek_v4_thinking_for_forced_tool_choice():
    llm = SimpleNamespace(
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )

    _messages, llm_kwargs = CitationPipeline(llm=llm).prepare_llm(
        "Alpha evidence.",
        "What evidence is available?",
    )

    assert llm_kwargs["tool_choice"] == "required"
    assert llm_kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_citation_pipeline_keeps_standard_tool_params_for_other_openai_models():
    llm = SimpleNamespace(
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
    )

    _messages, llm_kwargs = CitationPipeline(llm=llm).prepare_llm(
        "Alpha evidence.",
        "What evidence is available?",
    )

    assert llm_kwargs["tool_choice"] == "required"
    assert "extra_body" not in llm_kwargs
