"""Explicit validated message exchange; document fields never become provider data."""

from copy import deepcopy

from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.messages import AIMessageChunk
from langchain_core.messages import BaseMessage as LCBaseMessage
from langchain_core.messages import HumanMessage as LCHumanMessage
from langchain_core.messages import SystemMessage as LCSystemMessage

from .schema import AIMessage, BaseMessage, HumanMessage, SystemMessage

_COMMON = ("content", "additional_kwargs", "response_metadata", "name", "id")
_AI = ("example", "tool_calls", "invalid_tool_calls", "usage_metadata")
_EXTRAS = ("tool_call_id", "tool_call_chunks", "chunk_position")
_ROLES = {
    "system": (SystemMessage, LCSystemMessage),
    "human": (HumanMessage, LCHumanMessage),
    "ai": (AIMessage, LCAIMessage),
}


def to_langchain_message(message: BaseMessage) -> LCBaseMessage:
    """Create a native message, rejecting unknown extras instead of dropping them."""
    if not isinstance(message, BaseMessage):
        raise TypeError("Expected a MARA message")
    role = getattr(message, "type", None)
    if role not in _ROLES or not isinstance(message, _ROLES[role][0]):
        raise ValueError(f"Unsupported MARA message role: {role!r}")
    extras = message.model_extra or {}
    unknown = extras.keys() - set(_EXTRAS)
    if unknown:
        raise ValueError(
            f"Unmapped message fields: {sorted(unknown)}; use additional_kwargs explicitly"
        )
    fields = _COMMON + (
        _AI if role == "ai" else ("example",) if role == "human" else ()
    )
    payload = {key: deepcopy(getattr(message, key)) for key in fields}
    if not payload.get("example"):
        payload.pop("example", None)
    payload.update({key: deepcopy(extras[key]) for key in _EXTRAS if key in extras})
    native_class = AIMessageChunk if "tool_call_chunks" in payload else _ROLES[role][1]
    return native_class(**payload)


def from_langchain_message(message: LCBaseMessage) -> BaseMessage:
    """Copy native fields as data; allocate a separate internal document ID."""
    if not isinstance(message, LCBaseMessage):
        raise TypeError("Expected a native LangChain message")
    role = "ai" if isinstance(message, AIMessageChunk) else message.type
    if role not in _ROLES or not isinstance(message, _ROLES[role][1]):
        raise ValueError(f"Unsupported LangChain message role: {role!r}")
    fields = _COMMON + (
        _AI if role == "ai" else ("example",) if role == "human" else ()
    )
    allowed = set(fields) | set(_EXTRAS) | {"type"}
    unknown = (message.__dict__.keys() | (message.model_extra or {}).keys()) - allowed
    if unknown:
        raise ValueError(f"Unmapped native message fields: {sorted(unknown)}")
    payload = {
        key: deepcopy(
            getattr(message, key, False) if key == "example" else getattr(message, key)
        )
        for key in fields
    }
    payload.update(
        {
            key: deepcopy(getattr(message, key))
            for key in _EXTRAS
            if getattr(message, key, None) is not None
        }
    )
    # Reconstruct first so mutated or model_construct()-created objects are validated.
    native_class = (
        AIMessageChunk if isinstance(message, AIMessageChunk) else _ROLES[role][1]
    )
    validated = native_class(**payload)
    data = validated.model_dump(include=set(payload))
    return _ROLES[role][0](**deepcopy(data))
