from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifact_identifiers import namespace_token, safe_file_name
from .artifact_secure_fs import atomic_write_bytes
from .artifact_types import ArtifactNamespaceError


def artifact_output_path(
    root: str | Path,
    file_id: object,
    generation: object,
    file_name: str,
) -> Path:
    token = namespace_token(file_id)
    generation_token = namespace_token(generation)
    output_name = safe_file_name(file_name)
    return Path(root).expanduser().absolute() / token / generation_token / output_name


def write_chunk_artifacts(
    root: str | Path,
    docs: Sequence[Any],
    start_index: int,
    *,
    file_id: object | None = None,
    artifact_generation: object | None = None,
) -> None:
    if not docs:
        return
    metadata = docs[0].metadata
    file_name = metadata.get("file_name")
    file_id = file_id or metadata.get("file_id")
    artifact_generation = artifact_generation or metadata.get("artifact_generation")
    if not file_name or not file_id or not artifact_generation:
        return
    token = namespace_token(file_id)
    generation = namespace_token(artifact_generation)
    if any(doc.metadata.get("file_id") != file_id for doc in docs):
        raise ArtifactNamespaceError("Chunk batch contains multiple file identifiers")
    file_stem = Path(file_name).stem
    for offset, doc in enumerate(docs):
        leaf_name = safe_file_name(f"{file_stem}_{start_index + offset}.md")
        atomic_write_bytes(
            root,
            (token, generation),
            leaf_name,
            _chunk_markdown(doc).encode("utf-8"),
        )


def write_markdown_artifact(
    root: str | Path | None,
    source_file: str | Path,
    metadata: Mapping[str, Any],
    content: str,
) -> None:
    file_id = metadata.get("file_id")
    generation = metadata.get("artifact_generation")
    if root is None or not file_id or not generation:
        return
    token = namespace_token(file_id)
    generation_token = namespace_token(generation)
    leaf_name = safe_file_name(f"{Path(source_file).stem}.md")
    atomic_write_bytes(
        root,
        (token, generation_token),
        leaf_name,
        content.encode("utf-8"),
    )


def _chunk_markdown(doc: Any) -> str:
    content = ""
    if "page_label" in doc.metadata:
        content += f"Page label: {doc.metadata['page_label']}"
    if "file_name" in doc.metadata:
        content += f"\nFile name: {doc.metadata['file_name']}"
    if "section" in doc.metadata:
        content += f"\nSection: {doc.metadata['section']}"
    if doc.metadata.get("type") == "image":
        image_origin = f'<p><img src="{doc.metadata["image_origin"]}"></p>'
        content += f"\nImage origin: {image_origin}"
    if doc.text:
        content += f"\ntext:\n{doc.text}"
    return content


__all__ = [
    "artifact_output_path",
    "write_chunk_artifacts",
    "write_markdown_artifact",
]
