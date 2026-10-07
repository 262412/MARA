from __future__ import annotations

from typing import Any

from gradio import ChatInterface, skip
from gradio.components import Component, get_component_instance


class ChatBlock(ChatInterface):
    """PromptUI chat with additional outputs and an empty-message guard."""

    def __init__(
        self,
        *args,
        additional_outputs: str | Component | list[str | Component] | None = None,
        **kwargs,
    ):
        outputs = additional_outputs or []
        if not isinstance(outputs, list):
            outputs = [outputs]
        super().__init__(
            *args,
            additional_outputs=[get_component_instance(output) for output in outputs],
            **kwargs,
        )

    def _append_message_to_history(self, message, history, role="user"):
        if message == "":
            return history
        return super()._append_message_to_history(message, history, role)

    async def _submit_fn(self, message, history, *args) -> tuple[Any, ...]:
        if not message:
            return None, history, *[skip() for _ in self.additional_outputs]
        return await super()._submit_fn(message, history, *args)

    async def _stream_fn(self, message, history, *args):
        raise NotImplementedError("Stream function not implemented for ChatBlock")
