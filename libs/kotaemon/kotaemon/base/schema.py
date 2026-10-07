from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional, TypeVar
from uuid import uuid4

from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.messages import HumanMessage as LCHumanMessage
from langchain_core.messages import SystemMessage as LCSystemMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.messages.tool import InvalidToolCall, ToolCall
from llama_index.core.bridge.pydantic import Field
from llama_index.core.schema import Document as BaseDocument
from llama_index.core.schema import MediaResource, NodeRelationship
from pydantic import ConfigDict, model_serializer, model_validator

if TYPE_CHECKING:
    from haystack.schema import Document as HaystackDocument
    from openai.types.chat.chat_completion_message_param import (
        ChatCompletionMessageParam,
    )

IO_Type = TypeVar("IO_Type", "Document", str)
SAMPLE_TEXT = "A sample Document from kotaemon"


class Document(BaseDocument):
    """
    Base document class, mostly inherited from Document class from llama-index.

    This class accept one positional argument `content` of an arbitrary type, which will
        store the raw content of the document. If specified, the class will use
        `content` to initialize the base llama_index class.

    Attributes:
        content: raw content of the document, can be anything
        source: id of the source of the Document. Optional.
        channel: the channel to show the document. Optional.:
            - chat: show in chat message
            - info: show in information panel
            - index: show in index panel
            - debug: show in debug panel
    """

    content: Any = None
    source: Optional[str] = None
    channel: Optional[Literal["chat", "info", "index", "debug", "plot"]] = None
    id_: str = Field(default_factory=lambda: str(uuid4()), alias="doc_id")
    mimetype: str = "text/plain"
    start_char_idx: int | None = None
    end_char_idx: int | None = None

    def __init__(self, content: Optional[Any] = None, *args, **kwargs):
        if content is None:
            if kwargs.get("text", None) is not None:
                kwargs["content"] = kwargs["text"]
            elif kwargs.get("embedding", None) is not None:
                kwargs["content"] = kwargs["embedding"]
                # default text indicating this document only contains embedding
                kwargs["text"] = "<EMBEDDING>"
        elif isinstance(content, Document):
            # TODO: simplify the Document class
            temp_ = content.dict()
            temp_.update(kwargs)
            kwargs = temp_
        else:
            kwargs["content"] = content
            if content:
                kwargs["text"] = str(content)
            else:
                kwargs["text"] = ""
        if kwargs.get("text") == "":
            kwargs["text_resource"] = MediaResource(text=kwargs.pop("text"))
        super().__init__(*args, **kwargs)

    @property
    def text(self) -> str:
        return self.get_content()

    @text.setter
    def text(self, value: str) -> None:
        self.text_resource = MediaResource(text=value)

    @property
    def metadata_seperator(self) -> str:
        return self.metadata_separator

    @metadata_seperator.setter
    def metadata_seperator(self, value: str) -> None:
        self.metadata_separator = value

    @model_serializer(mode="wrap")
    def custom_model_dump(self, handler, info):
        """Keep MARA's existing text-document wire format, including nested messages."""
        data = handler(self)
        for name in (
            "text_resource",
            "image_resource",
            "audio_resource",
            "video_resource",
        ):
            data.pop(name, None)
        for internal, public in (
            ("metadata_separator", "metadata_seperator"),
            ("is_example", "example"),
        ):
            if internal not in type(self).model_fields:
                continue
            if internal in data:
                data[public] = data.pop(internal)
            if public in (info.exclude or {}):
                data.pop(public, None)
            elif info.include is not None and public in info.include:
                value = getattr(self, internal)
                field = type(self).model_fields[internal]
                if not (
                    (info.exclude_defaults and value == field.default)
                    or (info.exclude_unset and internal not in self.model_fields_set)
                ):
                    data[public] = value
        if "relationships" in data:
            data["relationships"] = {
                NodeRelationship[key].value
                if key in NodeRelationship.__members__
                else key: value
                for key, value in data["relationships"].items()
            }
        if (
            (info.include is None or "text" in info.include)
            and "text" not in (info.exclude or {})
            and not (info.exclude_defaults and self.text == "")
            and not (
                info.exclude_unset and "text_resource" not in self.model_fields_set
            )
        ):
            data["text"] = self.text
        data["class_name"] = self.class_name()
        return data

    def __bool__(self):
        return bool(self.content)

    @classmethod
    def example(cls) -> "Document":
        document = Document(
            text=SAMPLE_TEXT,
            metadata={"filename": "README.md", "category": "codebase"},
        )
        return document

    def to_haystack_format(self) -> "HaystackDocument":
        """Convert struct to Haystack document format."""
        from haystack.schema import Document as HaystackDocument

        metadata = self.metadata or {}
        text = self.text
        return HaystackDocument(content=text, meta=metadata)

    def to_langchain_format(self):
        """Convert directly without importing LlamaIndex's legacy provider bridge."""
        from langchain_core.documents import Document as LangchainDocument

        return LangchainDocument(
            page_content=self.text, metadata=self.metadata or {}, id=self.id_
        )

    def __str__(self):
        return str(self.content)


class DocumentWithEmbedding(Document):
    """Subclass of Document which must contains embedding

    Use this if you want to enforce component's IOs to must contain embedding.
    """

    def __init__(self, embedding: list[float], *args, **kwargs):
        kwargs["embedding"] = embedding
        super().__init__(*args, **kwargs)


class BaseMessage(Document):
    def __add__(self, other: Any):
        raise NotImplementedError

    def to_openai_format(self) -> "ChatCompletionMessageParam":
        raise NotImplementedError


class _RoleMessage(BaseMessage):
    """Preserve MARA's document record when messages cross provider boundaries."""

    model_config = ConfigDict(extra="allow")
    additional_kwargs: dict = Field(default_factory=dict)
    response_metadata: dict = Field(default_factory=dict)
    name: str | None = None
    id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def read_nested_legacy_record(cls, values):
        if isinstance(values, dict):
            if "class_name" in values and values["class_name"] != "Document":
                raise ValueError("Invalid nested message class_name; expected Document")
            return {key: value for key, value in values.items() if key != "class_name"}
        return values

    def __init__(self, content=None, *args, **kwargs):
        if (
            content is None
            and kwargs.get("text") is None
            and kwargs.get("embedding") is None
        ):
            raise TypeError("content or text is required")
        super().__init__(content, *args, **kwargs)


class SystemMessage(_RoleMessage, LCSystemMessage):
    type: Literal["system"] = "system"

    def to_openai_format(self) -> "ChatCompletionMessageParam":
        return {"role": "system", "content": self.content}


class AIMessage(_RoleMessage, LCAIMessage):
    type: Literal["ai"] = "ai"
    is_example: bool = Field(default=False, alias="example")
    tool_calls: list[ToolCall] = Field(default_factory=list)
    invalid_tool_calls: list[InvalidToolCall] = Field(default_factory=list)
    usage_metadata: UsageMetadata | None = None

    # Legacy messages expose a bool under Document's example classmethod name.
    @property  # type: ignore[override]
    def example(self) -> bool:
        return self.is_example

    @example.setter
    def example(self, value: bool) -> None:
        self.is_example = value

    @model_validator(mode="before")
    @classmethod
    def validate_tool_data(cls, values):
        if not isinstance(values, dict):
            raise ValueError("AI message fields must be a mapping")
        fields = (
            "additional_kwargs",
            "tool_calls",
            "invalid_tool_calls",
            "usage_metadata",
        )
        native = LCAIMessage(
            content="", **{key: values[key] for key in fields if key in values}
        )
        return {**values, **{key: native.model_dump()[key] for key in fields}}

    def to_openai_format(self) -> "ChatCompletionMessageParam":
        return {"role": "assistant", "content": self.content}


class HumanMessage(_RoleMessage, LCHumanMessage):
    type: Literal["human"] = "human"
    is_example: bool = Field(default=False, alias="example")

    # Preserve the same legacy public name without widening the field type.
    @property  # type: ignore[override]
    def example(self) -> bool:
        return self.is_example

    @example.setter
    def example(self, value: bool) -> None:
        self.is_example = value

    def to_openai_format(self) -> "ChatCompletionMessageParam":
        return {"role": "user", "content": self.content}


class RetrievedDocument(Document):
    """Subclass of Document with retrieval-related information

    Attributes:
        score (float): score of the document (from 0.0 to 1.0)
        retrieval_metadata (dict): metadata from the retrieval process, can be used
            by different components in a retrieved pipeline to communicate with each
            other
    """

    score: float = Field(default=0.0)
    retrieval_metadata: dict = Field(default={})


class LLMInterface(AIMessage):
    candidates: list[str] = Field(default_factory=list)
    completion_tokens: int = -1
    total_tokens: int = -1
    prompt_tokens: int = -1
    total_cost: float = 0
    logits: list[list[float]] = Field(default_factory=list)
    messages: list[AIMessage] = Field(default_factory=list)
    logprobs: list[float] = []


class StructuredOutputLLMInterface(LLMInterface):
    parsed: Any = None
    refusal: str = ""


class ExtractorOutput(Document):
    """
    Represents the output of an extractor.
    """

    matches: list[str]
