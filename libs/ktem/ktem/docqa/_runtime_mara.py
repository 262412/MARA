from __future__ import annotations

from typing import Any


class ResponseCapture:
    def __init__(self) -> None:
        self.agent_trace: list[dict[str, Any]] = []
        self.evidence_metadata: dict[str, Any] = {}
        self.artifact: Any = None

    def ingest(self, channel: str | None, content: Any) -> None:
        mara_channel = None
        mara_content = content
        if channel == "debug" and isinstance(content, dict):
            candidate = content.get("mara_channel")
            if candidate in {"agent_trace", "evidence_metadata", "artifact"}:
                mara_channel = candidate
                mara_content = content.get("payload")

        if channel == "agent_trace" or mara_channel == "agent_trace":
            if mara_content is None:
                self.agent_trace = []
            elif isinstance(mara_content, list):
                self.agent_trace.extend(mara_content)
            else:
                self.agent_trace.append(mara_content)
        elif channel == "evidence_metadata" or mara_channel == "evidence_metadata":
            if isinstance(mara_content, dict):
                self.evidence_metadata.update(mara_content)
            else:
                self.evidence_metadata["value"] = mara_content
        elif channel == "artifact" or mara_channel == "artifact":
            self.artifact = mara_content

    def as_response_kwargs(self) -> dict[str, Any]:
        return {
            "agent_trace": self.agent_trace,
            "evidence_metadata": self.evidence_metadata,
            "artifact": self.artifact,
        }


def apply_request_context(pipeline: Any, request: Any, graph_context: dict) -> None:
    pipeline.graph_context = graph_context
    pipeline.task_type = request.task_type or ""
    pipeline.agent_mode = request.agent_mode or getattr(pipeline, "agent_mode", "auto")
    pipeline.artifact_type = request.artifact_type or ""


def copy_request_fields(target: Any, source: Any) -> None:
    target.task_type = source.task_type
    target.agent_mode = source.agent_mode
    target.artifact_type = source.artifact_type


def selected_ids(runtime: Any, user_id: Any, selected_inputs: dict[int, Any]):
    file_index = runtime.file_index
    if file_index is None or file_index.id not in selected_inputs:
        return None
    return file_index.resolve_selected_ids(user_id, selected_inputs[file_index.id])
