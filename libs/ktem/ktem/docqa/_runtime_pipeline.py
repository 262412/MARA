from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_SETTING = "(default)"
STATE = {"app": {"regen": False}}


def apply_request_setting_overrides(
    settings: dict[str, Any],
    reasoning_id: str,
    request: Any,
) -> None:
    llm_setting_key = f"reasoning.options.{reasoning_id}.llm"
    if llm_setting_key in settings and request.llm not in (DEFAULT_SETTING, None, ""):
        settings[llm_setting_key] = request.llm
    if request.use_mindmap not in (DEFAULT_SETTING, None):
        settings["reasoning.options.simple.create_mindmap"] = request.use_mindmap
    if request.use_citation not in (DEFAULT_SETTING, None):
        settings["reasoning.options.simple.highlight_citation"] = request.use_citation
    if request.language not in (DEFAULT_SETTING, None, ""):
        settings["reasoning.lang"] = request.language


def build_reasoning_state(state: dict[str, Any] | None, reasoning_id: str) -> dict:
    source = state or STATE
    return {
        "app": deepcopy(source.get("app", STATE["app"])),
        "pipeline": deepcopy(source.get(reasoning_id, {})),
    }
