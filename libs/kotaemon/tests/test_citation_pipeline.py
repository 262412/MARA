from types import SimpleNamespace

import pytest

from kotaemon.indices.qa.citation import (
    CitationPipeline,
    CitationToolCallConfigurationError,
)
from kotaemon.llms import ChatLLM


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


def test_citation_pipeline_surfaces_tool_call_configuration_errors():
    class ToolCallBadRequest(Exception):
        status_code = 400

    class MisconfiguredLLM(ChatLLM):
        def invoke(self, _messages, **_kwargs):
            raise ToolCallBadRequest(
                'tool_choice="required" requires --tool-call-parser to be set'
            )

    with pytest.raises(CitationToolCallConfigurationError):
        CitationPipeline(llm=MisconfiguredLLM()).invoke(
            "Alpha evidence.",
            "What evidence is available?",
        )
