"""First-party agents and native LangChain tools through real model wrappers."""

import json

import httpx
import pytest
from pydantic import BaseModel

from kotaemon.agents import AgentType, BaseTool, LangchainAgent, ReactAgent
from kotaemon.agents.tools.base import ToolException
from kotaemon.base import AIMessage, HumanMessage, LLMInterface, Node, SystemMessage
from kotaemon.chatbot.base import BaseChatBot, ChatConversation
from kotaemon.llms.chats.langchain_based import LCChatOpenAI


class Query(BaseModel):
    query: str


class LookupTool(BaseTool):
    name = "lookup"
    description = "Look up the synthetic value."
    args_schema = Query

    def _run_tool(self, query):
        if query == "error":
            raise ToolException("synthetic tool error")
        return "value=" + query


@pytest.fixture
def agent_model():
    requests = []

    def answer(request):
        payload = json.loads(request.content)
        requests.append(payload)
        text = (
            "Action: lookup\nAction Input: value"
            if len(requests) == 1
            else "Final Answer: completed"
        )
        return httpx.Response(
            200,
            json={
                "id": "request-id",
                "object": "chat.completion",
                "created": 1,
                "model": "synthetic",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        model = LCChatOpenAI(
            openai_api_key="synthetic",
            openai_api_base="https://example.invalid/v1",
            model="synthetic",
            max_retries=0,
            http_client=client,
        )
        yield model, requests


def test_actual_native_langchain_agent_loop_tools_and_scratchpad(agent_model):
    model, requests = agent_model
    agent = LangchainAgent(
        llm=model, plugins=[LookupTool()], agent_type=AgentType.react
    )
    result = agent("Find a value")
    assert result.status == "finished" and result.text == "completed"
    assert len(requests) == 2
    assert "value=value" in json.dumps(requests[1])
    assert result.type == "agent" and isinstance(result, LLMInterface)


def test_first_party_react_stream_tool_step_and_close(agent_model):
    model, requests = agent_model
    agent = ReactAgent(llm=model, plugins=[LookupTool()])
    stream = agent.stream("Find a value")
    first = next(stream)
    assert first.status == "thinking"
    assert first.intermediate_steps[-1] == "value=value"
    stream.close()
    assert len(requests) == 1


def test_first_party_react_stream_completes_and_retains_history(agent_model):
    model, requests = agent_model
    agent = ReactAgent(llm=model, plugins=[LookupTool()])
    result = list(agent.stream("Find a value"))
    assert [item.status for item in result] == ["thinking", "finished"]
    assert result[-1].text == "completed"
    assert len(requests) == 2
    assert "value=value" in json.dumps(requests[-1])


def test_tool_validation_and_error_policy_remain_real():
    tool = LookupTool(handle_tool_error=True)
    assert tool({"query": "value"}) == "value=value"
    assert tool({"query": "error"}) == "synthetic tool error"
    with pytest.raises(ValueError):
        tool({})
    with pytest.raises(ValueError):
        tool({"query": ["not-a-string"]})
    assert tool.to_langchain_format().invoke("value") == "value=value"


class ConversationBot(BaseChatBot):
    llm = Node()

    def run(self, messages):
        return self.llm(messages)


def test_conversation_history_order_and_output_role(agent_model):
    model, requests = agent_model
    conversation = ChatConversation(bot=ConversationBot(llm=model))
    conversation.history.extend(
        [SystemMessage("system"), HumanMessage("old question"), AIMessage("old answer")]
    )
    response = conversation.run(HumanMessage("new question"))
    assert isinstance(response, AIMessage)
    assert [m["role"] for m in requests[0]["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert [m.type for m in conversation.history] == [
        "system",
        "human",
        "ai",
        "human",
        "ai",
    ]
