import json

import pytest
from langchain_core.messages import AIMessage as LangchainAIMessage
from langchain_core.messages import HumanMessage as LangchainHumanMessage
from langchain_core.messages import SystemMessage as LangchainSystemMessage

from kotaemon.base.schema import (
    AIMessage,
    Document,
    HumanMessage,
    RetrievedDocument,
    SystemMessage,
)


def test_message_schema_uses_langchain_core_messages():
    assert issubclass(AIMessage, LangchainAIMessage)
    assert issubclass(HumanMessage, LangchainHumanMessage)
    assert issubclass(SystemMessage, LangchainSystemMessage)


@pytest.mark.parametrize(
    ("message_type", "langchain_type", "role"),
    [
        (SystemMessage, LangchainSystemMessage, "system"),
        (HumanMessage, LangchainHumanMessage, "user"),
        (AIMessage, LangchainAIMessage, "assistant"),
    ],
)
def test_message_json_preserves_both_public_model_contracts(
    message_type, langchain_type, role
):
    message = message_type(
        content="synthetic message",
        doc_id="synthetic-message",
        metadata={"page_label": "iv"},
    )
    restored = message_type.from_dict(json.loads(json.dumps(message.to_dict())))

    assert isinstance(restored, Document)
    assert isinstance(restored, langchain_type)
    assert restored.doc_id == "synthetic-message"
    assert restored.metadata == {"page_label": "iv"}
    assert restored.to_openai_format() == {"role": role, "content": "synthetic message"}


def test_document_reads_existing_serialized_field_names():
    # Synthetic payload produced by the LlamaIndex 0.10.68.post1 baseline.
    serialized: dict[str, object] = {
        "id_": "synthetic-doc",
        "embedding": None,
        "metadata": {"filename": "synthetic.pdf", "page_label": "iv"},
        "excluded_embed_metadata_keys": [],
        "excluded_llm_metadata_keys": [],
        "relationships": {},
        "text": "synthetic text",
        "mimetype": "text/plain",
        "start_char_idx": None,
        "end_char_idx": None,
        "text_template": "{metadata_str}\n\n{content}",
        "metadata_template": "{key}: {value}",
        "metadata_seperator": "\n",
        "content": "synthetic text",
        "source": None,
        "channel": None,
        "class_name": "Document",
    }
    restored = Document.from_dict(json.loads(json.dumps(serialized)))

    assert restored.doc_id == "synthetic-doc"
    assert restored.text == restored.content == "synthetic text"
    assert restored.metadata == serialized["metadata"]
    assert restored.to_dict() == serialized


def test_document_alias_and_invalid_channel_remain_distinct():
    document = Document(text="synthetic text", doc_id="synthetic-doc", channel="info")

    assert document.id_ == document.doc_id == "synthetic-doc"
    assert document.channel == "info"
    with pytest.raises(ValueError, match="channel"):
        Document(text="synthetic text", channel="invalid")


def test_retrieval_metadata_defaults_are_not_shared():
    first = RetrievedDocument(text="first")
    second = RetrievedDocument(text="second")
    first.retrieval_metadata["only_first"] = True

    assert second.retrieval_metadata == {}
    assert second.score == 0.0
