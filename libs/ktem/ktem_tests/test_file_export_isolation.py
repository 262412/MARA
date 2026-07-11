from __future__ import annotations

import json
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import gradio as gr
import pytest
from ktem.index.file._scoped_page import ScopedFileIndexPageMixin
from ktem.index.file._selection_service import FileSelectionError
from ktem.index.file.pipelines import IndexPipeline
from theflow.settings import settings as flowsettings

from kotaemon.base import Document
from kotaemon.indices.vectorindex import VectorIndexing
from kotaemon.loaders.azureai_document_intelligence_loader import (
    AzureAIDocumentIntelligenceLoader,
)
from kotaemon.loaders.html_loader import MhtmlReader

GENERATION = "generation-a"


class _SelectionService:
    def __init__(self, names, barrier: threading.Barrier | None = None):
        self.names = names
        self.barrier = barrier

    def source_name(self, file_id, user_id):
        if self.barrier is not None:
            self.barrier.wait()
        try:
            return self.names[(file_id, user_id)]
        except KeyError as exc:
            raise FileSelectionError("source unavailable") from exc


class _Page(ScopedFileIndexPageMixin):
    def __init__(self, selection_service):
        self.selection_service = selection_service

    def _get_file_selection_service(self):
        return self.selection_service


@pytest.fixture
def artifact_roots(tmp_path, monkeypatch):
    roots = SimpleNamespace(
        chunks=tmp_path / "chunks",
        markdown=tmp_path / "markdown",
        zip=tmp_path / "zip",
    )
    for root in (roots.chunks, roots.markdown, roots.zip):
        root.mkdir()
    monkeypatch.setattr(flowsettings, "MARA_AUTH_MODE", "auto", raising=False)
    monkeypatch.setattr(
        flowsettings, "KH_CHUNKS_OUTPUT_DIR", str(roots.chunks), raising=False
    )
    monkeypatch.setattr(
        flowsettings, "KH_MARKDOWN_OUTPUT_DIR", str(roots.markdown), raising=False
    )
    monkeypatch.setattr(
        flowsettings, "KH_ZIP_OUTPUT_DIR", str(roots.zip), raising=False
    )
    return roots


def _artifact_path(root: Path, file_id: str, name: str, content: str) -> Path:
    path = root / file_id / GENERATION / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _manifest_path(roots, file_id: str) -> Path:
    return roots.zip / "manifests" / "v1" / file_id / "manifest.json"


def _write_manifest(roots, file_id: str, entries: list[dict[str, str]]) -> Path:
    path = _manifest_path(roots, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "file_id": file_id, "entries": entries}),
        encoding="utf-8",
    )
    return path


def _entry(kind: str, file_id: str, name: str) -> dict[str, str]:
    return {
        "kind": kind,
        "relative_path": f"{file_id}/{GENERATION}/{name}",
    }


def _download_value(result) -> Path:
    value = result[1].value
    if isinstance(value, dict):
        value = value["path"]
    return Path(value)


def _zip_contents(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}


def test_single_download_excludes_same_stem_other_file_id(artifact_roots):
    own_id = "file-owner"
    victim_id = "file-victim"
    _artifact_path(artifact_roots.chunks, own_id, "report_0.md", "OWNER CHUNK")
    _artifact_path(artifact_roots.markdown, own_id, "report.md", "OWNER MARKDOWN")
    _artifact_path(artifact_roots.chunks, victim_id, "report_0.md", "VICTIM CHUNK")
    _write_manifest(
        artifact_roots,
        own_id,
        [
            _entry("chunks", own_id, "report_0.md"),
            _entry("markdown", own_id, "report.md"),
        ],
    )
    page = _Page(
        _SelectionService(
            {(own_id, "owner"): "report.pdf", (victim_id, "victim"): "report.pdf"}
        )
    )

    contents = _zip_contents(
        _download_value(page.download_single_file(False, own_id, "owner"))
    )

    assert contents == {
        "chunks/report_0.md": "OWNER CHUNK",
        "markdown/report.md": "OWNER MARKDOWN",
    }
    assert "VICTIM" not in "".join(contents.values())


def test_single_download_does_not_match_stem_substrings(artifact_roots):
    file_id = "file-alpha"
    _artifact_path(artifact_roots.chunks, file_id, "alpha_0.md", "EXACT")
    _write_manifest(
        artifact_roots,
        file_id,
        [_entry("chunks", file_id, "alpha_0.md")],
    )
    (artifact_roots.chunks / "alphabet_0.md").write_text(
        "SUBSTRING VICTIM", encoding="utf-8"
    )
    page = _Page(_SelectionService({(file_id, "owner"): "alpha.pdf"}))

    contents = _zip_contents(
        _download_value(page.download_single_file(False, file_id, "owner"))
    )

    assert contents == {"chunks/alpha_0.md": "EXACT"}


def test_chunk_and_markdown_paths_are_unique_per_file_id(artifact_roots, tmp_path):
    vector_writer = SimpleNamespace(cache_dir=str(artifact_roots.chunks), count_=0)
    for file_id, marker in (("file-a", "OWNER"), ("file-b", "VICTIM")):
        VectorIndexing.write_chunk_to_file(
            cast(VectorIndexing, vector_writer),
            [
                Document(
                    text=marker,
                    metadata={
                        "file_id": file_id,
                        "file_name": "report.pdf",
                        "artifact_generation": GENERATION,
                    },
                )
            ],
        )

    mhtml_paths = []
    for file_id, marker in (("file-a", "OWNER HTML"), ("file-b", "VICTIM HTML")):
        source = tmp_path / file_id / "report.mhtml"
        source.parent.mkdir()
        source.write_text(
            "MIME-Version: 1.0\n"
            'Content-Type: text/html; charset="utf-8"\n\n'
            f"<html><body>{marker}</body></html>",
            encoding="utf-8",
        )
        MhtmlReader(
            cache_dir=str(artifact_roots.markdown), open_encoding="utf-8"
        ).load_data(
            source,
            extra_info={
                "file_id": file_id,
                "artifact_generation": GENERATION,
            },
        )
        mhtml_paths.append(artifact_roots.markdown / file_id / GENERATION / "report.md")

    assert (
        artifact_roots.chunks / "file-a" / GENERATION / "report_0.md"
    ).read_text() != (
        artifact_roots.chunks / "file-b" / GENERATION / "report_0.md"
    ).read_text()
    assert [path.read_text() for path in mhtml_paths] == ["OWNER HTML", "VICTIM HTML"]

    azure_paths = []
    for file_id, marker in (("file-c", "OWNER AZURE"), ("file-d", "VICTIM AZURE")):
        source = tmp_path / file_id / "azure" / "report.pdf"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"pdf")
        result = SimpleNamespace(content=marker, pages=[])
        result.get = lambda _key, default=None: default
        loader = SimpleNamespace(
            cache_dir=str(artifact_roots.markdown),
            figure_friendly_filetypes=[],
            vlm_endpoint=None,
            _analyze_document=lambda _path, value=result: value,
        )
        AzureAIDocumentIntelligenceLoader.load_data(
            cast(AzureAIDocumentIntelligenceLoader, loader),
            source,
            extra_info={
                "file_id": file_id,
                "artifact_generation": GENERATION,
            },
        )
        azure_paths.append(artifact_roots.markdown / file_id / GENERATION / "report.md")

    assert [path.read_text() for path in azure_paths] == [
        "OWNER AZURE",
        "VICTIM AZURE",
    ]


def test_download_rejects_manifest_entry_outside_file_namespace(artifact_roots):
    file_id = "file-owner"
    _artifact_path(artifact_roots.chunks, "file-victim", "secret.md", "VICTIM")
    _write_manifest(
        artifact_roots,
        file_id,
        [_entry("chunks", file_id, "../file-victim/secret.md")],
    )
    page = _Page(_SelectionService({(file_id, "owner"): "report.pdf"}))

    with pytest.raises(gr.Error, match="reindex"):
        page.download_single_file(False, file_id, "owner")


@pytest.mark.parametrize("attack", ["symlink", "duplicate"])
def test_download_rejects_manifest_symlink_and_duplicate_archive_name(
    artifact_roots, attack
):
    file_id = "file-owner"
    target = _artifact_path(artifact_roots.chunks, file_id, "chunk.md", "OWNER")
    entries = [_entry("chunks", file_id, "chunk.md")]
    if attack == "symlink":
        link = target.with_name("link.md")
        link.symlink_to(target)
        entries = [_entry("chunks", file_id, "link.md")]
    else:
        entries.append(_entry("chunks", file_id, "chunk.md"))
    _write_manifest(artifact_roots, file_id, entries)
    page = _Page(_SelectionService({(file_id, "owner"): "report.pdf"}))

    with pytest.raises(gr.Error, match="reindex"):
        page.download_single_file(False, file_id, "owner")


def test_missing_manifest_never_falls_back_to_legacy_stem_files(artifact_roots):
    file_id = "file-owner"
    (artifact_roots.chunks / "report_0.md").write_text(
        "UNTRUSTED LEGACY", encoding="utf-8"
    )
    page = _Page(_SelectionService({(file_id, "owner"): "report.pdf"}))

    with pytest.raises(gr.Error, match="reindex"):
        page.download_single_file(False, file_id, "owner")
    with pytest.raises(gr.Error, match="reindex"):
        page.download_single_file(False, file_id, "other-user")


def test_same_stem_concurrent_downloads_use_distinct_output_paths(artifact_roots):
    file_id = "file-owner"
    _artifact_path(artifact_roots.chunks, file_id, "report_0.md", "OWNER")
    _write_manifest(
        artifact_roots,
        file_id,
        [_entry("chunks", file_id, "report_0.md")],
    )
    page = _Page(
        _SelectionService(
            {(file_id, "owner"): "report.pdf"}, barrier=threading.Barrier(2)
        )
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: page.download_single_file(False, file_id, "owner"),
                range(2),
            )
        )

    paths = [_download_value(result) for result in results]
    assert paths[0] != paths[1]
    assert all(_zip_contents(path) == {"chunks/report_0.md": "OWNER"} for path in paths)


def test_simple_html_downloads_do_not_share_same_stem_output(artifact_roots):
    file_id = "file-owner"
    page = _Page(_SelectionService({(file_id, "owner"): "report.pdf"}))

    first = _download_value(
        page.download_single_file_simple(False, "OWNER ONE", file_id, "owner")
    )
    second = _download_value(
        page.download_single_file_simple(False, "OWNER TWO", file_id, "owner")
    )

    assert first != second
    assert first.read_text(encoding="utf-8") == "OWNER ONE"
    assert second.read_text(encoding="utf-8") == "OWNER TWO"
    server_outputs = sorted(artifact_roots.zip.rglob("*.html"))
    assert len(server_outputs) == 2
    assert server_outputs[0].parent != server_outputs[1].parent
    assert {path.read_text(encoding="utf-8") for path in server_outputs} == {
        "OWNER ONE",
        "OWNER TWO",
    }


def test_failed_indexing_does_not_publish_downloadable_manifest(
    artifact_roots, tmp_path
):
    source = tmp_path / "report.txt"
    source.write_text("source", encoding="utf-8")

    def run(file_id: str, *, fail: bool):
        pipeline = SimpleNamespace(collection_name="test")
        pipeline.get_id_if_exists = lambda _path: None
        pipeline.store_file = lambda _path: file_id
        pipeline.load_docs_with_parse_cache = lambda *_args: SimpleNamespace(
            documents=[Document(text="chunk", metadata={"file_id": file_id})],
            cache_hit=False,
            stats={"hits": 0, "misses": 1, "writes": 0},
        )

        def handle_docs(_docs, produced_file_id, _file_name):
            _artifact_path(
                artifact_roots.chunks,
                produced_file_id,
                "report_0.md",
                produced_file_id,
            )
            yield Document(text="indexed", channel="debug")

        def finish(*_args):
            if fail:
                raise RuntimeError("finish failed")

        pipeline.handle_docs = handle_docs
        pipeline.finish = finish
        return list(IndexPipeline.stream(cast(IndexPipeline, pipeline), source, False))

    run("file-success", fail=False)
    with pytest.raises(RuntimeError, match="finish failed"):
        run("file-failed", fail=True)

    assert json.loads(_manifest_path(artifact_roots, "file-success").read_text()) == {
        "version": 1,
        "file_id": "file-success",
        "entries": [
            {
                "kind": "chunks",
                "relative_path": (f"file-success/{GENERATION}/report_0.md"),
            }
        ],
    }
    assert not _manifest_path(artifact_roots, "file-failed").exists()
