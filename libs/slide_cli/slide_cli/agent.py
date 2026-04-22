from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kotaemon.modelcli import ModelRequest, build_registry, load_runtime_config, run_completion

from .deck import DeckPatch, TextReplaceOp, load_deck_snapshot


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
                        None if item.get("before_text") is None else str(item.get("before_text"))
                    ),
                    after_text=str(item["after_text"]),
                )
            )
        except Exception:
            continue

    return DeckPatch(summary=str(patch_payload.get("summary", "")), edits=edits)


@dataclass(slots=True)
class SlideAgentRunner:
    input_path: str
    model: str = "gpt-4o-mini"
    provider: str | None = None
    config_path: str = "modelcli.yml"
    cwd: str | None = None
    max_iterations: int = 4
    shell_timeout_sec: int = 15
    workspace_root: Path = field(init=False)
    snapshot: Any = field(init=False)

    def __post_init__(self) -> None:
        self.input_path = str(Path(self.input_path).resolve())
        self.workspace_root = self._resolve_workspace_root(self.cwd, self.input_path)
        self.snapshot = load_deck_snapshot(self.input_path)

    def run(self, user_prompt: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        history = list(history or [])
        observations: list[dict[str, Any]] = []
        raw_responses: list[str] = []
        cfg = load_runtime_config(self.config_path if Path(self.config_path).exists() else None)
        registry = build_registry()

        for _ in range(self.max_iterations):
            prompt = self._build_prompt(
                user_prompt=user_prompt,
                history_text=_history_excerpt(history),
                observations=observations,
            )
            response = run_completion(
                registry=registry,
                cfg=cfg,
                request=ModelRequest(prompt=prompt, model=self.model),
                provider=self.provider,
            )
            raw_responses.append(str(response.text))
            decoded = _extract_json_object(response.text)

            if not decoded:
                break

            response_type = str(decoded.get("type", "")).strip().lower()
            if response_type == "tool":
                tool_name = str(decoded.get("tool", "")).strip()
                tool_input = decoded.get("input", "")
                try:
                    observation_text = self._execute_tool(tool_name, tool_input)
                except Exception as exc:
                    observation_text = f"Tool error: {exc}"
                observations.append(
                    {
                        "tool": tool_name,
                        "input": tool_input,
                        "output": observation_text,
                    }
                )
                continue

            if response_type == "final" or "assistant_response" in decoded or "patch" in decoded:
                return {
                    "assistant_response": str(decoded.get("assistant_response", "")).strip()
                    or "Completed slide rewrite analysis.",
                    "patch": _coerce_patch(decoded),
                    "observations": observations,
                    "raw_responses": raw_responses,
                }

        final_text = raw_responses[-1] if raw_responses else "No response generated."
        return {
            "assistant_response": final_text.strip() or "No response generated.",
            "patch": None,
            "observations": observations,
            "raw_responses": raw_responses,
        }

    def _build_prompt(
        self,
        *,
        user_prompt: str,
        history_text: str,
        observations: list[dict[str, Any]],
    ) -> str:
        observation_text = "(none)"
        if observations:
            lines = []
            for item in observations[-6:]:
                lines.append(f"TOOL {item['tool']} INPUT {item['input']}")
                lines.append(f"OBSERVATION: {item['output']}")
            observation_text = "\n".join(lines)

        return (
            "You are Slide CLI, a slide-focused coding and editing harness.\n"
            "You may inspect the deck, inspect files in the working directory, and run limited shell commands before deciding on a final patch.\n"
            "Available tools:\n"
            "- inspect_deck: ignore input, returns a structured summary of the entire deck.\n"
            "- read_slide: input is a slide number like `1`, returns one slide summary.\n"
            "- list_files: ignore input, returns files under the current workspace root.\n"
            "- read_file: input is a relative or absolute file path inside the workspace root.\n"
            "- search_text: input is a text pattern, searches the deck summary.\n"
            "- run_shell: input is a shell command to execute inside the workspace root.\n\n"
            "Return JSON only.\n"
            "If you need a tool, return:\n"
            '{"type":"tool","tool":"read_slide","input":"1","reason":"brief reason"}\n'
            "When you are done, return:\n"
            "{"
            '"type":"final",'
            '"assistant_response":"short user-facing response",'
            '"patch":{"summary":"what changed","edits":[{"slide_number":1,"target_id":"slide-1/shape-2/text","before_text":"old","after_text":"new"}]}'
            "}\n"
            "If no deck change is needed, return an empty edits list.\n\n"
            f"Working directory: {self.workspace_root}\n"
            f"Deck path: {self.input_path}\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Tool observations:\n{observation_text}\n\n"
            f"Deck summary:\n{self.snapshot.summary_text(max_chars=180)}\n\n"
            f"User request:\n{user_prompt}\n"
        )

    def _execute_tool(self, tool_name: str, tool_input: Any) -> str:
        normalized = str(tool_name or "").strip()
        if normalized == "inspect_deck":
            return self.snapshot.summary_text(max_chars=180)
        if normalized == "read_slide":
            slide_number = int(str(tool_input or "1").strip())
            for slide in self.snapshot.slides:
                if slide.slide_number == slide_number:
                    return slide.summary_text(max_chars=180)
            return f"Slide {slide_number} was not found."
        if normalized == "list_files":
            paths = sorted(
                str(path.relative_to(self.workspace_root))
                for path in self.workspace_root.iterdir()
            )
            return "\n".join(paths[:200]) or "(no files)"
        if normalized == "read_file":
            path = self._resolve_workspace_path(str(tool_input or ""))
            return path.read_text(encoding="utf-8", errors="replace")[:4000]
        if normalized == "search_text":
            pattern = str(tool_input or "").strip().lower()
            if not pattern:
                return "No pattern provided."
            matches = [
                line
                for line in self.snapshot.summary_text(max_chars=240).splitlines()
                if pattern in line.lower()
            ]
            return "\n".join(matches[:50]) or "No matches found."
        if normalized == "run_shell":
            command = str(tool_input or "").strip()
            if not command:
                return "No command provided."
            completed = subprocess.run(
                command,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                shell=True,
                timeout=self.shell_timeout_sec,
            )
            stdout = completed.stdout.strip()
            stderr = completed.stderr.strip()
            return (
                f"returncode: {completed.returncode}\n"
                f"stdout:\n{stdout or '(empty)'}\n"
                f"stderr:\n{stderr or '(empty)'}"
            )
        return f"Unknown tool '{normalized}'."

    @staticmethod
    def _resolve_workspace_root(cwd: str | None, input_path: str) -> Path:
        if cwd:
            return Path(cwd).resolve()
        return Path(input_path).resolve().parent

    def _resolve_workspace_path(self, candidate: str) -> Path:
        value = str(candidate or "").strip()
        if not value:
            raise FileNotFoundError("No file path provided.")
        path = Path(value)
        resolved = path.resolve() if path.is_absolute() else (self.workspace_root / path).resolve()

        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise PermissionError(f"Path '{resolved}' is outside the workspace root.") from exc

        if not resolved.exists():
            raise FileNotFoundError(resolved)
        return resolved
