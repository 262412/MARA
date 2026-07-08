from __future__ import annotations

import os
from typing import Any

DEFAULT_GRADIO_SERVER_PORT = 7860


def resolve_gradio_server_port(port: Any = None) -> int:
    if str(port or "").strip():
        return int(port)

    env_port = (
        os.getenv("GRADIO_SERVER_PORT", "").strip() or os.getenv("PORT", "").strip()
    )
    if env_port:
        return int(env_port)
    return DEFAULT_GRADIO_SERVER_PORT
