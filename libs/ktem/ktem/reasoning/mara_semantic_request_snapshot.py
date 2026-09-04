from __future__ import annotations

from copy import deepcopy
from typing import Any

from kotaemon.base import SystemMessage


def model_request_snapshot(
    messages: list[Any],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "messages": [
            {
                "role": "system" if isinstance(message, SystemMessage) else "user",
                "content": str(getattr(message, "content", "") or ""),
            }
            for message in messages
        ],
        "parameters": deepcopy(parameters),
    }
