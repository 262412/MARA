from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Type

from pydantic import BaseModel, Field

from kotaemon.agents.tools import BaseTool
from kotaemon.agents.tools.base import ToolException

from .deck import DeckSnapshot, export_deck_pdf


@dataclass(slots=True)
class SlideToolContext:
    input_path: Path
    workspace_root: Path
    snapshot: DeckSnapshot
    shell_timeout_sec: int = 15
    export_pdf_func: Callable[..., Path] = export_deck_pdf
    max_file_chars: int = 4000
    max_listed_paths: int = 200

    def resolve_workspace_path(
        self, candidate: str | Path, *, allow_missing: bool = False
    ) -> Path:
        raw_value = str(candidate or "").strip()
        if not raw_value:
            raise ToolException("No file path provided.")

        path = Path(raw_value)
        resolved = (
            path.resolve()
            if path.is_absolute()
            else (self.workspace_root / path).resolve()
        )
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ToolException(
                f"Path '{resolved}' is outside the workspace root."
            ) from exc

        if not allow_missing and not resolved.exists():
            raise ToolException(f"Path '{resolved}' does not exist.")
        return resolved

    def inspect_deck(self) -> str:
        return self.snapshot.summary_text(max_chars=180)

    def read_slide(self, slide_number: int) -> str:
        for slide in self.snapshot.slides:
            if slide.slide_number == slide_number:
                return slide.summary_text(max_chars=180)
        return f"Slide {slide_number} was not found."

    def list_files(self) -> str:
        paths = sorted(
            str(path.relative_to(self.workspace_root))
            for path in self.workspace_root.rglob("*")
            if path.is_file()
        )
        return "\n".join(paths[: self.max_listed_paths]) or "(no files)"

    def read_file(self, path: str) -> str:
        resolved = self.resolve_workspace_path(path)
        return resolved.read_text(encoding="utf-8", errors="replace")[
            : self.max_file_chars
        ]

    def write_file(self, *, path: str, content: str, append: bool = False) -> str:
        resolved = self.resolve_workspace_path(path, allow_missing=True)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with resolved.open(mode, encoding="utf-8") as file_obj:
            file_obj.write(content)
        return f"Wrote {len(content)} characters to {resolved}"

    def search_text(self, query: str) -> str:
        pattern = str(query or "").strip().lower()
        if not pattern:
            return "No pattern provided."
        matches = [
            line
            for line in self.snapshot.summary_text(max_chars=240).splitlines()
            if pattern in line.lower()
        ]
        return "\n".join(matches[:50]) or "No matches found."

    def extract_slide_text(self, slide_number: int | None = None) -> str:
        slides = self.snapshot.slides
        if slide_number is not None:
            slides = tuple(
                slide
                for slide in self.snapshot.slides
                if slide.slide_number == slide_number
            )
            if not slides:
                return f"Slide {slide_number} was not found."

        chunks: list[str] = []
        for slide in slides:
            chunks.append(f"Slide {slide.slide_number}: {slide.title or '(untitled)'}")
            for shape in slide.shapes:
                text = " ".join(shape.text.split()).strip()
                if text:
                    chunks.append(f"- {shape.target_id}: {text}")
        return "\n".join(chunks) if chunks else "(empty)"

    def review_deck(self) -> str:
        total_shapes = sum(len(slide.shapes) for slide in self.snapshot.slides)
        empty_targets = [
            shape.target_id
            for slide in self.snapshot.slides
            for shape in slide.shapes
            if not shape.text.strip()
        ]
        untitled_slides = [
            slide.slide_number
            for slide in self.snapshot.slides
            if not slide.title.strip()
        ]
        long_targets = [
            shape.target_id
            for slide in self.snapshot.slides
            for shape in slide.shapes
            if len(" ".join(shape.text.split())) > 180
        ]
        payload = {
            "slide_count": self.snapshot.slide_count,
            "text_target_count": total_shapes,
            "untitled_slides": untitled_slides,
            "empty_targets": empty_targets[:20],
            "long_targets": long_targets[:20],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def run_shell(self, command: str) -> str:
        raw_command = str(command or "").strip()
        if not raw_command:
            return "No command provided."
        try:
            completed = subprocess.run(
                raw_command,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                shell=True,
                timeout=self.shell_timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolException(
                f"Command timed out after {self.shell_timeout_sec} seconds: {raw_command}"
            ) from exc
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        return (
            f"returncode: {completed.returncode}\n"
            f"stdout:\n{stdout or '(empty)'}\n"
            f"stderr:\n{stderr or '(empty)'}"
        )

    def export_pdf(self, output_path: str | None = None) -> str:
        try:
            exported = self.export_pdf_func(self.input_path, output_path=output_path)
        except Exception as exc:
            raise ToolException(str(exc)) from exc
        return f"Exported PDF to {exported}"


class SlideNumberArgs(BaseModel):
    slide_number: int = Field(..., description="Target slide number.")


class FilePathArgs(BaseModel):
    path: str = Field(..., description="Path inside the workspace root.")


class WriteFileArgs(BaseModel):
    path: str = Field(..., description="Path inside the workspace root.")
    content: str = Field(..., description="UTF-8 text content to write.")
    append: bool = Field(default=False, description="Append instead of overwrite.")


class SearchArgs(BaseModel):
    query: str = Field(..., description="Case-insensitive search string.")


class ExtractSlideTextArgs(BaseModel):
    slide_number: int | None = Field(default=None, description="Optional slide number.")


class ExportPdfArgs(BaseModel):
    output_path: str | None = Field(
        default=None, description="Optional output PDF path."
    )


class ShellArgs(BaseModel):
    command: str = Field(..., description="Shell command to execute.")


class _SlideTool(BaseTool):
    tool_ctx: SlideToolContext
    handle_tool_error = True

    @staticmethod
    def _validate_schema(args_schema: Type[BaseModel], payload):
        if hasattr(args_schema, "model_validate"):
            return args_schema.model_validate(payload)
        return args_schema.parse_obj(payload)

    @staticmethod
    def _schema_field_names(args_schema: Type[BaseModel]) -> list[str]:
        model_fields = getattr(args_schema, "model_fields", None)
        if isinstance(model_fields, dict):
            return list(model_fields.keys())
        legacy_fields = getattr(args_schema, "__fields__", None)
        if isinstance(legacy_fields, dict):
            return list(legacy_fields.keys())
        return []

    @staticmethod
    def _dump_schema(model: BaseModel) -> dict:
        if hasattr(model, "model_dump"):
            return model.model_dump()
        return model.dict()

    def _parse_input(self, tool_input):
        args_schema = self.args_schema
        if isinstance(tool_input, str) and args_schema is not None:
            stripped_input = tool_input.strip()
            if stripped_input.startswith("{") or stripped_input.startswith("["):
                try:
                    parsed_input = json.loads(stripped_input)
                except json.JSONDecodeError as exc:
                    raise ToolException(f"Invalid JSON tool input: {exc}") from exc
                result = self._validate_schema(args_schema, parsed_input)
                dumped = self._dump_schema(result)
                if isinstance(parsed_input, dict):
                    return {k: v for k, v in dumped.items() if k in parsed_input}
                return dumped
            key_ = self._schema_field_names(args_schema)[0]
            self._validate_schema(args_schema, {key_: tool_input})
            return tool_input

        if not isinstance(tool_input, str) and args_schema is not None:
            result = self._validate_schema(args_schema, tool_input)
            dumped = self._dump_schema(result)
            return {k: v for k, v in dumped.items() if k in tool_input}

        return tool_input


class InspectDeckTool(_SlideTool):
    name: str = "inspect_deck"
    description: str = "Return a concise structured summary of the whole deck."

    def _run_tool(self, *_args, **_kwargs) -> str:
        return self.tool_ctx.inspect_deck()


class ReadSlideTool(_SlideTool):
    name: str = "read_slide"
    description: str = "Read one slide summary. Input should be a slide number."
    args_schema: Optional[Type[BaseModel]] = SlideNumberArgs

    def _run_tool(self, slide_number: int) -> str:
        return self.tool_ctx.read_slide(int(slide_number))


class ListFilesTool(_SlideTool):
    name: str = "list_files"
    description: str = "List files under the current workspace root."

    def _run_tool(self, *_args, **_kwargs) -> str:
        return self.tool_ctx.list_files()


class ReadFileTool(_SlideTool):
    name: str = "read_file"
    description: str = "Read one UTF-8 text file from the workspace root."
    args_schema: Optional[Type[BaseModel]] = FilePathArgs

    def _run_tool(self, path: str) -> str:
        return self.tool_ctx.read_file(path)


class WriteFileTool(_SlideTool):
    name: str = "write_file"
    description: str = (
        "Write or append a UTF-8 text file under the workspace root. "
        "Input should be JSON with `path`, `content`, and optional `append`."
    )
    args_schema: Optional[Type[BaseModel]] = WriteFileArgs

    def _run_tool(self, path: str, content: str, append: bool = False) -> str:
        return self.tool_ctx.write_file(path=path, content=content, append=append)


class SearchTextTool(_SlideTool):
    name: str = "search_text"
    description: str = "Search the deck summary for matching text."
    args_schema: Optional[Type[BaseModel]] = SearchArgs

    def _run_tool(self, query: str) -> str:
        return self.tool_ctx.search_text(query)


class ExtractSlideTextTool(_SlideTool):
    name: str = "extract_slide_text"
    description: str = (
        "Extract plain text from the whole deck or a specific slide. "
        "Input can be a slide number or JSON with `slide_number`."
    )
    args_schema: Optional[Type[BaseModel]] = ExtractSlideTextArgs

    def _run_tool(self, slide_number: int | None = None) -> str:
        if slide_number is None:
            return self.tool_ctx.extract_slide_text()
        return self.tool_ctx.extract_slide_text(int(slide_number))


class ReviewDeckTool(_SlideTool):
    name: str = "review_deck"
    description: str = "Return deterministic review heuristics for the current deck."

    def _run_tool(self, *_args, **_kwargs) -> str:
        return self.tool_ctx.review_deck()


class ExportPdfTool(_SlideTool):
    name: str = "export_pdf"
    description: str = (
        "Export the current deck to PDF through LibreOffice. "
        "Input can be empty or JSON with `output_path`."
    )
    args_schema: Optional[Type[BaseModel]] = ExportPdfArgs

    def _run_tool(self, output_path: str | None = None) -> str:
        return self.tool_ctx.export_pdf(output_path=output_path)


class RunShellTool(_SlideTool):
    name: str = "run_shell"
    description: str = "Run one shell command inside the workspace root."
    args_schema: Optional[Type[BaseModel]] = ShellArgs

    def _run_tool(self, command: str) -> str:
        return self.tool_ctx.run_shell(command)


def build_default_tools(context: SlideToolContext) -> list[BaseTool]:
    return [
        InspectDeckTool(tool_ctx=context),
        ReadSlideTool(tool_ctx=context),
        ListFilesTool(tool_ctx=context),
        ReadFileTool(tool_ctx=context),
        WriteFileTool(tool_ctx=context),
        SearchTextTool(tool_ctx=context),
        ExtractSlideTextTool(tool_ctx=context),
        ReviewDeckTool(tool_ctx=context),
        ExportPdfTool(tool_ctx=context),
        RunShellTool(tool_ctx=context),
    ]


__all__ = [
    "SlideToolContext",
    "build_default_tools",
]
