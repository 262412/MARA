from __future__ import annotations

from pathlib import Path

import pytest

from kotaemon.artifact_cache import ArtifactDocuments
from kotaemon.base import Document
from kotaemon.indices.parse_cache import load_data_with_parse_cache
from kotaemon.loaders.unstructured_loader import UnstructuredReader


class _PathSensitiveArtifactReader:
    artifact_cache_version = 1

    def __init__(self):
        self.calls: list[tuple[str, str | None]] = []
        self.published_sidecars: list[str] = []

    def load_data(self, file_path: Path, extra_info=None):
        suffix = file_path.suffix.casefold()
        content_type = UnstructuredReader._infer_content_type(
            str(file_path), extra_info
        )
        self.calls.append((suffix, content_type))
        parse_context = f"{suffix}:{content_type}"
        document = Document(
            text=f"text:{parse_context}",
            metadata={
                "file_name": file_path.name,
                "file_path": str(file_path.resolve()),
                "source_suffix": suffix,
                "effective_mime": content_type,
            },
        )
        document.content = f"content:{parse_context}"
        return ArtifactDocuments(
            [document],
            artifact_sidecar={"markdown": f"artifact:{parse_context}"},
        )

    def write_cached_artifact(
        self,
        _file_path,
        *,
        extra_info,
        documents,
        artifact_sidecar,
    ):
        del extra_info, documents
        self.published_sidecars.append(artifact_sidecar["markdown"])


class _PathLikeMetadataReader:
    def __init__(self, metadata_key: str):
        self.metadata_key = metadata_key
        self.calls = 0

    def load_data(self, file_path: Path, extra_info=None):
        del extra_info
        self.calls += 1
        return [
            Document(
                text="path-like metadata",
                metadata={self.metadata_key: file_path},
            )
        ]


def test_parse_cache_separates_path_derived_suffix_and_mime_context(tmp_path):
    html_source = tmp_path / "same.html"
    text_source = tmp_path / "same.txt"
    html_source.write_bytes(b"identical bytes")
    text_source.write_bytes(b"identical bytes")
    reader = _PathSensitiveArtifactReader()

    html = load_data_with_parse_cache(
        reader,
        html_source,
        extra_info={"file_id": "html-source"},
        cache_dir=tmp_path / "parse-cache",
    )
    text = load_data_with_parse_cache(
        reader,
        text_source,
        extra_info={"file_id": "text-source"},
        cache_dir=tmp_path / "parse-cache",
    )

    assert reader.calls == [(".html", "text/html"), (".txt", "text/plain")]
    assert html.cache_hit is False
    assert text.cache_hit is False
    assert html.cache_key != text.cache_key
    assert (html.documents[0].text, html.documents[0].content) == (
        "text:.html:text/html",
        "content:.html:text/html",
    )
    assert (text.documents[0].text, text.documents[0].content) == (
        "text:.txt:text/plain",
        "content:.txt:text/plain",
    )
    assert text.documents[0].metadata["effective_mime"] == "text/plain"
    assert reader.published_sidecars == [
        "artifact:.html:text/html",
        "artifact:.txt:text/plain",
    ]


def test_parse_cache_replays_current_path_metadata_for_same_parse_context(tmp_path):
    first_source = tmp_path / "first.txt"
    second_source = tmp_path / "second.txt"
    first_source.write_bytes(b"identical bytes")
    second_source.write_bytes(b"identical bytes")
    reader = _PathSensitiveArtifactReader()

    first = load_data_with_parse_cache(
        reader,
        first_source,
        extra_info={"file_id": "first-source"},
        cache_dir=tmp_path / "parse-cache",
    )
    second = load_data_with_parse_cache(
        reader,
        second_source,
        extra_info={"file_id": "second-source"},
        cache_dir=tmp_path / "parse-cache",
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert reader.calls == [(".txt", "text/plain")]
    assert second.documents[0].metadata["file_id"] == "second-source"
    assert second.documents[0].metadata["file_name"] == "second.txt"
    assert second.documents[0].metadata["file_path"] == str(second_source.resolve())


@pytest.mark.parametrize("metadata_key", ["file_path", "source"])
def test_parse_cache_replays_current_path_for_pathlike_metadata(
    tmp_path,
    metadata_key,
):
    first_source = tmp_path / "first.txt"
    second_source = tmp_path / "second.txt"
    first_source.write_bytes(b"identical bytes")
    second_source.write_bytes(b"identical bytes")
    reader = _PathLikeMetadataReader(metadata_key)

    first = load_data_with_parse_cache(
        reader,
        first_source,
        cache_dir=tmp_path / "parse-cache",
    )
    second = load_data_with_parse_cache(
        reader,
        second_source,
        cache_dir=tmp_path / "parse-cache",
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert reader.calls == 1
    assert second.documents[0].metadata[metadata_key] == str(second_source.resolve())
