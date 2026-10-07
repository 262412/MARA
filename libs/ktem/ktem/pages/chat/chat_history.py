"""Keep saved conversation turns at the Gradio messages transport boundary."""

import gradio as gr


class ConversationChatbot(gr.Chatbot):
    is_template = True

    def postprocess(self, value):
        messages = []
        for turn in value or []:
            if not isinstance(turn, (list, tuple)) or len(turn) != 2:
                raise ValueError("Conversation history requires two-item turns")
            for role, content in zip(("user", "assistant"), turn):
                if content is not None and not isinstance(content, str):
                    raise ValueError("Conversation turns require text or None")
                messages.append(
                    {
                        "role": role,
                        "content": "" if content is None else content,
                        "metadata": {"id": "mara-empty"} if content is None else None,
                    }
                )
        return super().postprocess(messages)

    def preprocess(self, payload):
        messages = super().preprocess(payload)
        if len(messages) % 2:
            raise ValueError("Conversation history requires complete turn pairs")
        turns = []
        for index in range(0, len(messages), 2):
            turn = []
            for role, message in zip(
                ("user", "assistant"), messages[index : index + 2]
            ):
                content = message["content"]
                if (
                    message["role"] != role
                    or len(content) != 1
                    or content[0]["type"] != "text"
                ):
                    raise ValueError(
                        "Conversation history requires paired text messages"
                    )
                missing = (message.get("metadata") or {}).get("id") == "mara-empty"
                turn.append(None if missing else content[0]["text"])
            turns.append(turn)
        return turns


def message_position(index):
    """Map current transport positions to the saved [turn, role] coordinates."""
    return [index // 2, index % 2] if isinstance(index, int) else index


def feedback_value(value):
    """Store the selected text, keeping the pre-migration feedback record shape."""
    if not isinstance(value, dict):
        return value
    content = value.get("content")
    if isinstance(content, str):
        return content
    if (
        isinstance(content, list)
        and len(content) == 1
        and content[0].get("type") == "text"
    ):
        return (
            None
            if (value.get("metadata") or {}).get("id") == "mara-empty"
            else content[0]["text"]
        )
    raise ValueError("Conversation feedback requires a text message")
