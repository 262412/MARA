from langchain_core.messages import AIMessage as LangchainAIMessage
from langchain_core.messages import HumanMessage as LangchainHumanMessage
from langchain_core.messages import SystemMessage as LangchainSystemMessage

from kotaemon.base.schema import AIMessage, HumanMessage, SystemMessage


def test_message_schema_uses_langchain_core_messages():
    assert issubclass(AIMessage, LangchainAIMessage)
    assert issubclass(HumanMessage, LangchainHumanMessage)
    assert issubclass(SystemMessage, LangchainSystemMessage)
