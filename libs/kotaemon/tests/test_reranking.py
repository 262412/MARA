import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openai.types.chat.chat_completion import ChatCompletion

from kotaemon.base import Document
from kotaemon.indices.rankings import LLMReranking
from kotaemon.indices.rankings.cohere import CohereReranking
from kotaemon.llms import AzureChatOpenAI

_openai_chat_completion_responses = [
    ChatCompletion.parse_obj(
        {
            "id": "chatcmpl-7qyuw6Q1CFCpcKsMdFkmUPUa7JP2x",
            "object": "chat.completion",
            "created": 1692338378,
            "model": "gpt-35-turbo",
            "system_fingerprint": None,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": text,
                        "function_call": None,
                        "tool_calls": None,
                    },
                    "logprobs": None,
                }
            ],
            "usage": {"completion_tokens": 9, "prompt_tokens": 10, "total_tokens": 19},
        }
    )
    for text in [
        "YES",
        "NO",
        "YES",
    ]
]


@pytest.fixture
def llm():
    return AzureChatOpenAI(
        api_key="dummy",
        api_version="2024-05-01-preview",
        azure_deployment="gpt-4o",
        azure_endpoint="https://test.openai.azure.com/",
    )


@patch(
    "openai.resources.chat.completions.Completions.create",
    side_effect=_openai_chat_completion_responses,
)
def test_reranking(openai_completion, llm):
    documents = [Document(text=f"test {idx}") for idx in range(3)]
    query = "test query"

    reranker = LLMReranking(llm=llm, concurrent=False)
    rerank_docs = reranker(documents, query=query)

    assert len(rerank_docs) == 2


def test_cohere_reranking_uses_injected_api_key_resolver(monkeypatch):
    client_calls = {}

    class _FakeClient:
        def __init__(self, api_key):
            client_calls["api_key"] = api_key

        def rerank(self, *, model, query, documents):
            client_calls["model"] = model
            client_calls["query"] = query
            client_calls["documents"] = documents
            return SimpleNamespace(
                results=[SimpleNamespace(index=0, relevance_score=0.91)]
            )

    monkeypatch.setitem(sys.modules, "cohere", SimpleNamespace(Client=_FakeClient))

    reranker = CohereReranking(
        cohere_api_key="",
        cohere_api_key_resolver=lambda: "resolved-key",
    )
    documents = [Document(text="alpha")]

    reranked = reranker.run(documents, query="alpha?")

    assert client_calls == {
        "api_key": "resolved-key",
        "model": reranker.model_name,
        "query": "alpha?",
        "documents": ["alpha"],
    }
    assert reranked[0].metadata["reranking_score"] == 0.91
