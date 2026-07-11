from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from ktem.index.file.pipelines import IndexPipeline
from theflow.settings import settings as flowsettings

from kotaemon.artifact_namespace import finish_and_publish_artifacts
from kotaemon.base import Document
from kotaemon.indices.parse_cache import load_data_with_parse_cache
from kotaemon.loaders.azureai_document_intelligence_loader import (
    AzureAIDocumentIntelligenceLoader,
)
from kotaemon.loaders.html_loader import MhtmlReader

FILE_ID = "file-owner"


@pytest.fixture
def roots(tmp_path, monkeypatch):
    result = SimpleNamespace(
        chunks=tmp_path / "chunks",
        markdown=tmp_path / "markdown",
        zip=tmp_path / "zip",
        parse=tmp_path / "parse",
    )
    for root in vars(result).values():
        root.mkdir()
    monkeypatch.setattr(
        flowsettings, "KH_CHUNKS_OUTPUT_DIR", str(result.chunks), raising=False
    )
    monkeypatch.setattr(
        flowsettings, "KH_MARKDOWN_OUTPUT_DIR", str(result.markdown), raising=False
    )
    monkeypatch.setattr(
        flowsettings, "KH_ZIP_OUTPUT_DIR", str(result.zip), raising=False
    )
    return result


def _stream_probe(source: Path, capture):
    pipeline = SimpleNamespace(collection_name="test")
    pipeline.get_id_if_exists = lambda _path: None
    pipeline.store_file = lambda _path: FILE_ID

    def load_docs(_path, extra_info):
        capture(dict(extra_info))
        raise RuntimeError("stop after parse metadata")

    pipeline.load_docs_with_parse_cache = load_docs
    return IndexPipeline.stream(cast(IndexPipeline, pipeline), source, False)


def test_stream_assigns_fresh_generation_before_parse_cache_lookup(tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("source", encoding="utf-8")
    seen: list[dict[str, object]] = []

    for _ in range(2):
        with pytest.raises(RuntimeError, match="stop after parse metadata"):
            list(_stream_probe(source, seen.append))

    generations = [item.get("artifact_generation") for item in seen]
    assert all(generations)
    assert generations[0] != generations[1]


def test_stream_strips_generation_before_docstore_and_passes_it_explicitly(tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("source", encoding="utf-8")
    captured = {}
    pipeline = SimpleNamespace(collection_name="test")
    pipeline.get_id_if_exists = lambda _path: None
    pipeline.store_file = lambda _path: FILE_ID

    def load_docs(_path, extra_info):
        return SimpleNamespace(
            documents=[Document(text="chunk", metadata=dict(extra_info))],
            cache_hit=False,
            stats={"hits": 0, "misses": 1, "writes": 0},
        )

    def handle_docs(docs, _file_id, _file_name, artifact_generation=None):
        captured["metadata"] = dict(docs[0].metadata)
        captured["generation"] = artifact_generation
        yield Document(text="indexed", channel="debug")

    def finish(*_args):
        raise RuntimeError("stop after handle docs")

    pipeline.load_docs_with_parse_cache = load_docs
    pipeline.handle_docs = handle_docs
    pipeline.finish = finish

    with pytest.raises(RuntimeError, match="stop after handle docs"):
        list(IndexPipeline.stream(cast(IndexPipeline, pipeline), source, False))

    assert captured["generation"]
    assert "artifact_generation" not in captured["metadata"]


def _mhtml_source(path: Path) -> None:
    path.write_text(
        "MIME-Version: 1.0\n"
        'Content-Type: text/html; charset="utf-8"\n\n'
        "<html><body>CACHED MHTML</body></html>",
        encoding="utf-8",
    )


def test_mhtml_parse_cache_miss_and_hit_publish_current_generation(roots, tmp_path):
    source = tmp_path / "report.mhtml"
    _mhtml_source(source)
    reader = MhtmlReader(cache_dir=str(roots.markdown), open_encoding="utf-8")

    first = load_data_with_parse_cache(
        reader,
        source,
        extra_info={"file_id": FILE_ID, "artifact_generation": "generation-a"},
        cache_dir=roots.parse,
    )
    second = load_data_with_parse_cache(
        reader,
        source,
        extra_info={"file_id": FILE_ID, "artifact_generation": "generation-b"},
        cache_dir=roots.parse,
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    for generation in ("generation-a", "generation-b"):
        output = roots.markdown / FILE_ID / generation / "report.md"
        assert output.read_text(encoding="utf-8") == "CACHED MHTML"


class _AzureResult(dict):
    def __init__(self):
        super().__init__(figures=[], tables=[])
        self.content = "CACHED AZURE"
        self.pages = []


def test_azure_parse_cache_miss_and_hit_publish_current_generation(
    roots, tmp_path, monkeypatch
):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4")
    reader = AzureAIDocumentIntelligenceLoader(
        endpoint="endpoint",
        credential="key",
        cache_dir=str(roots.markdown),
    )
    monkeypatch.setattr(reader, "_analyze_document", lambda _path: _AzureResult())

    first = load_data_with_parse_cache(
        reader,
        source,
        extra_info={"file_id": FILE_ID, "artifact_generation": "generation-a"},
        cache_dir=roots.parse,
    )
    second = load_data_with_parse_cache(
        reader,
        source,
        extra_info={"file_id": FILE_ID, "artifact_generation": "generation-b"},
        cache_dir=roots.parse,
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    for generation in ("generation-a", "generation-b"):
        output = roots.markdown / FILE_ID / generation / "report.md"
        assert output.read_text(encoding="utf-8") == "CACHED AZURE"


def test_manifest_publication_scans_only_current_generation(roots, tmp_path):
    for generation, marker in (("generation-old", "OLD"), ("generation-new", "NEW")):
        path = roots.chunks / FILE_ID / generation / "report_0.md"
        path.parent.mkdir(parents=True)
        path.write_text(marker, encoding="utf-8")
    pipeline = SimpleNamespace(
        _artifact_generation="generation-new",
        _artifact_writer_future=None,
        finish=lambda *_args: None,
    )
    settings = SimpleNamespace(
        KH_CHUNKS_OUTPUT_DIR=str(roots.chunks),
        KH_MARKDOWN_OUTPUT_DIR=str(roots.markdown),
        KH_ZIP_OUTPUT_DIR=str(roots.zip),
    )

    finish_and_publish_artifacts(
        pipeline,
        FILE_ID,
        tmp_path / "source.pdf",
        settings,
    )

    manifest = roots.zip / "manifests" / "v1" / FILE_ID / "manifest.json"
    entries = json.loads(manifest.read_text(encoding="utf-8"))["entries"]
    assert entries == [
        {
            "kind": "chunks",
            "relative_path": f"{FILE_ID}/generation-new/report_0.md",
        }
    ]


def test_quick_handle_docs_exposes_background_writer_future(tmp_path):
    started = threading.Event()
    release = threading.Event()
    pipeline = SimpleNamespace(
        chunk_batch_size=200,
        last_indexing_status=None,
        splitter=None,
        run_embedding_in_thread=True,
        VS=None,
        handle_chunks_docstore=lambda *_args: None,
    )

    def handle_vector(*_args):
        started.set()
        release.wait()

    pipeline.handle_chunks_vectorstore = handle_vector
    docs = [Document(text="chunk", metadata={"type": "text"})]

    try:
        list(
            IndexPipeline.handle_docs(
                cast(IndexPipeline, pipeline),
                docs,
                FILE_ID,
                "report.pdf",
            )
        )
        assert started.wait(timeout=2)
        assert pipeline._artifact_writer_future is not None
    finally:
        release.set()
