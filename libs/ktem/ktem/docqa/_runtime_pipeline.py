from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_SETTING = "(default)"
STATE = {"app": {"regen": False}}
STRUCTURED_QA_PROMPT_GUARD = (
    "\n\nAnswer formatting requirements:\n"
    "- Return the final answer as Markdown, not raw HTML.\n"
    "- Do not return one unbroken paragraph.\n"
    "- Put a blank line between paragraphs, headings, lists, formulas, and tables.\n"
    "- If the user asks for a table, comparison, matrix, or summary table, "
    "include a Markdown table with a header and separator row, for example:\n"
    "| Aspect | Summary |\n"
    "| --- | --- |\n"
    "| Key idea | Concise evidence-grounded summary |\n"
    "- Put a blank line before and after each table; never write pipe-delimited "
    "table rows inline inside a paragraph.\n"
    "- Render mathematical formulas as LaTeX with $...$ for inline math and "
    "$$...$$ for display math. Do not use backticks for mathematical variables "
    "or equations.\n"
    "- Render code as fenced Markdown code blocks with triple backticks such as "
    "```python when a language tag is clear.\n"
)


def apply_request_setting_overrides(
    settings: dict[str, Any],
    reasoning_id: str,
    request: Any,
) -> None:
    _ensure_structured_qa_prompt(settings, reasoning_id)
    llm_setting_key = f"reasoning.options.{reasoning_id}.llm"
    if llm_setting_key in settings and request.llm not in (DEFAULT_SETTING, None, ""):
        settings[llm_setting_key] = request.llm
    if request.use_mindmap not in (DEFAULT_SETTING, None):
        settings["reasoning.options.simple.create_mindmap"] = request.use_mindmap
    if request.use_citation not in (DEFAULT_SETTING, None):
        settings["reasoning.options.simple.highlight_citation"] = request.use_citation
    if request.language not in (DEFAULT_SETTING, None, ""):
        settings["reasoning.lang"] = request.language


def _ensure_structured_qa_prompt(settings: dict[str, Any], reasoning_id: str) -> None:
    prompt_key = f"reasoning.options.{reasoning_id}.qa_prompt"
    prompt = settings.get(prompt_key)
    if not isinstance(prompt, str):
        return
    if "Return the final answer as Markdown" in prompt:
        return
    settings[prompt_key] = prompt.rstrip() + STRUCTURED_QA_PROMPT_GUARD


def build_reasoning_state(state: dict[str, Any] | None, reasoning_id: str) -> dict:
    source = state or STATE
    return {
        "app": deepcopy(source.get("app", STATE["app"])),
        "pipeline": deepcopy(source.get(reasoning_id, {})),
    }
