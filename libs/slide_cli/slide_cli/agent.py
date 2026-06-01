from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kotaemon.agents import ReactAgent
from kotaemon.agents.io import AgentAction
from kotaemon.base import LLMInterface
from kotaemon.llms import BaseLLM, PromptTemplate
from kotaemon.modelcli import (
    ModelRequest,
    build_registry,
    load_runtime_config,
    run_completion,
)

from .config import SlideAgentConfig
from .deck import DeckPatch, TextReplaceOp, export_deck_pdf, load_deck_snapshot
from .tools import SlideToolContext, build_default_tools


def _strip_fence(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    text = _strip_fence(raw_text)
    candidates = [text]
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        candidates.append(match.group(1))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _extract_final_answer_text(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    marker = "Final Answer:"
    if marker in text:
        return text.split(marker, maxsplit=1)[-1].strip()
    return text


def _history_excerpt(events: list[dict[str, Any]], max_items: int = 6) -> str:
    if not events:
        return "(none)"

    lines = []
    for event in events[-max_items:]:
        role = str(event.get("role", "unknown")).upper()
        kind = str(event.get("kind", "")).upper()
        content = str(event.get("content", "")).strip()
        if not content:
            continue
        prefix = f"{role}/{kind}" if kind else role
        lines.append(f"{prefix}: {content}")
    return "\n".join(lines) if lines else "(none)"


def _coerce_patch(payload: dict[str, Any] | None) -> DeckPatch | None:
    if not payload:
        return None
    patch_payload = payload.get("patch")
    if not isinstance(patch_payload, dict):
        return None

    edits = []
    for item in patch_payload.get("edits") or []:
        if not isinstance(item, dict):
            continue
        try:
            edits.append(
                TextReplaceOp(
                    slide_number=int(item["slide_number"]),
                    target_id=str(item["target_id"]),
                    before_text=(
                        None
                        if item.get("before_text") is None
                        else str(item.get("before_text"))
                    ),
                    after_text=str(item["after_text"]),
                )
            )
        except Exception:
            continue

    return DeckPatch(summary=str(patch_payload.get("summary", "")), edits=edits)


def _collect_observations(
    intermediate_steps: list[tuple[Any, str]] | None
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for action, observation in intermediate_steps or []:
        if not isinstance(action, AgentAction):
            continue
        observations.append(
            {
                "tool": action.tool,
                "input": action.tool_input,
                "output": str(observation),
            }
        )
    return observations


def _collect_raw_responses(
    intermediate_steps: list[tuple[Any, str]] | None, final_text: str
) -> list[str]:
    responses = [
        action.log for action, _observation in intermediate_steps or [] if action
    ]
    if final_text and (
        not responses or str(responses[-1]).strip() != final_text.strip()
    ):
        responses.append(final_text)
    return [str(item) for item in responses if str(item).strip()]


SLIDE_REACT_PROMPT = PromptTemplate(
    template=(
        "You are MARA's top-level agent line.\n"
        "This is a high-permission workflow for deck work plus workspace-side file changes.\n"
        "Use the available tools deliberately and keep your reasoning concise.\n"
        "You must follow this exact format:\n\n"
        "Question: the user request you must solve\n"
        "Thought: reason briefly about the next best step\n"
        "Action: the tool to call, must be one of [{tool_names}]\n"
        "Action Input: the tool input. Use either a plain string or compact JSON.\n"
        "Observation: the tool result\n"
        "... (repeat Thought/Action/Action Input/Observation as needed)\n"
        "Thought: I now know the final answer\n"
        "Final Answer: a single JSON object with keys `assistant_response` and `patch`\n\n"
        "Rules:\n"
        "- `patch` must be an object like "
        '{{"summary":"what changed","edits":[{{"slide_number":1,"target_id":"slide-1/shape-2/text","before_text":"old","after_text":"new"}}]}}\n'
        "- If no deck change is needed, return `patch` with an empty `edits` list.\n"
        "- Tools that accept structured input should receive compact JSON in Action Input.\n"
        "- Do not wrap the final JSON in markdown fences.\n\n"
        "Available tools:\n"
        "{tool_description}\n"
        "Conversation language: {lang}\n\n"
        "Question: {instruction}\n"
        "Thought:{agent_scratchpad}"
    )
)


class ModelCliLLM(BaseLLM):
    model: str
    provider: str | None = None
    config_path: str = "modelcli.yml"

    def _complete(self, prompt: str) -> LLMInterface:
        cfg = load_runtime_config(
            self.config_path if Path(self.config_path).exists() else None
        )
        registry = build_registry()
        response = run_completion(
            registry=registry,
            cfg=cfg,
            request=ModelRequest(prompt=prompt, model=self.model),
            provider=self.provider,
        )
        return LLMInterface(text=str(response.text))

    def to_langchain_format(self):
        raise NotImplementedError("ModelCliLLM does not expose a LangChain adapter.")

    def invoke(self, prompt: str, *args, **kwargs) -> LLMInterface:
        return self._complete(prompt)

    async def ainvoke(self, prompt: str, *args, **kwargs) -> LLMInterface:
        return self._complete(prompt)

    def stream(self, prompt: str, *args, **kwargs):
        yield self._complete(prompt)

    async def astream(self, prompt: str, *args, **kwargs):
        yield self._complete(prompt)


@dataclass(slots=True)
class SlideAgentRunner:
    input_path: str
    config: SlideAgentConfig | None = None
    model: str = "gpt-4o-mini"
    provider: str | None = None
    config_path: str = "modelcli.yml"
    cwd: str | None = None
    max_iterations: int = 4
    shell_timeout_sec: int = 15
    workspace_root: Path = field(init=False)
    snapshot: Any = field(init=False)
    tools: list[Any] = field(init=False)
    tool_map: dict[str, Any] = field(init=False)
    agent: ReactAgent = field(init=False)

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = SlideAgentConfig(
                cwd=self.cwd,
                shell_timeout_sec=self.shell_timeout_sec,
                model=self.model,
                provider=self.provider,
                config_path=self.config_path,
                max_iterations=self.max_iterations,
            )
        self.model = self.config.model
        self.provider = self.config.provider
        self.config_path = self.config.config_path
        self.max_iterations = self.config.max_iterations
        self.shell_timeout_sec = self.config.shell_timeout_sec
        self.input_path = str(Path(self.input_path).resolve())
        self.workspace_root = self._resolve_workspace_root(
            self.config.cwd, self.input_path
        )
        self.snapshot = load_deck_snapshot(self.input_path)
        tool_context = SlideToolContext(
            input_path=Path(self.input_path),
            workspace_root=self.workspace_root,
            snapshot=self.snapshot,
            shell_timeout_sec=self.shell_timeout_sec,
            export_pdf_func=export_deck_pdf,
        )
        self.tools = build_default_tools(tool_context)
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.agent = ReactAgent(
            llm=ModelCliLLM(
                model=self.model,
                provider=self.provider,
                config_path=self.config_path,
            ),
            plugins=self.tools,
            max_iterations=self.max_iterations,
            prompt_template=SLIDE_REACT_PROMPT,
        )

    def run(
        self, user_prompt: str, history: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        history = list(history or [])
        instruction = self._build_instruction(
            user_prompt=user_prompt,
            history_text=_history_excerpt(history),
        )
        result = self.agent.run(instruction, max_iterations=self.max_iterations)
        final_text = str(result.text or "").strip()
        observations = _collect_observations(result.intermediate_steps)
        raw_responses = _collect_raw_responses(result.intermediate_steps, final_text)
        decoded = _extract_json_object(_extract_final_answer_text(final_text))

        if decoded and ("assistant_response" in decoded or "patch" in decoded):
            return {
                "assistant_response": str(decoded.get("assistant_response", "")).strip()
                or "Completed slide rewrite analysis.",
                "patch": _coerce_patch(decoded),
                "observations": observations,
                "raw_responses": raw_responses,
            }

        return {
            "assistant_response": final_text.strip() or "No response generated.",
            "patch": None,
            "observations": observations,
            "raw_responses": raw_responses,
        }

    def _build_instruction(
        self,
        *,
        user_prompt: str,
        history_text: str,
    ) -> str:
        return (
            "You are working inside the top-level MARA CLI agent line.\n"
            "This is the high-permission workflow for deck work plus workspace-side file changes.\n"
            "Inspect the deck, inspect the workspace when needed, and produce a structured slide patch when deck changes are required.\n\n"
            f"Working directory: {self.workspace_root}\n"
            f"Deck path: {self.input_path}\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Deck summary:\n{self.snapshot.summary_text(max_chars=180)}\n\n"
            f"User request:\n{user_prompt}\n"
        )

    def _execute_tool(self, tool_name: str, tool_input: Any) -> str:
        normalized = str(tool_name or "").strip()
        tool = self.tool_map.get(normalized)
        if tool is None:
            available = ", ".join(sorted(self.tool_map))
            return f"Unknown tool '{normalized}'. Available tools: {available}"
        return str(tool.run(tool_input))

    @staticmethod
    def _resolve_workspace_root(cwd: str | None, input_path: str) -> Path:
        if cwd:
            return Path(cwd).resolve()
        return Path(input_path).resolve().parent
