"""Candidate-only automatic PDF cache identity contracts."""

import importlib.metadata
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from llama_index.readers.file import PDFReader
from tenacity import RetryError

from kotaemon.indices.parse_cache import (
    build_parse_cache_key,
    load_data_with_parse_cache,
)
from kotaemon.loaders import AutoReader, PDFThumbnailReader

from .test_pdf_reading_contracts import write_pdf


class FullPDFReader(PDFReader):
    def __init__(self):
        super().__init__(return_full_document=True)


def test_auto_reader_selection_and_suffix_are_part_of_identity(tmp_path):
    path = write_pdf(tmp_path / "reader.pdf")
    pages = AutoReader("PDFReader")
    full = AutoReader(FullPDFReader)
    assert build_parse_cache_key(pages, path) != build_parse_cache_key(full, path)
    first = load_data_with_parse_cache(pages, path, cache_dir=tmp_path / "cache")
    second = load_data_with_parse_cache(full, path, cache_dir=tmp_path / "cache")
    assert len(first.documents) == 3 and len(second.documents) == 1
    assert not first.cache_hit and not second.cache_hit
    renamed = tmp_path / "reader.bin"
    renamed.write_bytes(path.read_bytes())
    assert build_parse_cache_key(pages, renamed) != first.cache_key
    key = build_parse_cache_key(pages, renamed)
    real = importlib.metadata.version
    with patch(
        "importlib.metadata.version",
        side_effect=lambda name: "other" if name == "pypdf" else real(name),
    ):
        assert build_parse_cache_key(pages, renamed) != key


def test_unavailable_reader_source_bypasses_instead_of_using_an_unknown_key(tmp_path):
    path = write_pdf(tmp_path / "source.pdf")
    with patch("inspect.getfile", side_effect=OSError("implementation unavailable")):
        with pytest.warns(RuntimeWarning, match="implementation unavailable"):
            result = load_data_with_parse_cache(
                PDFReader(), path, cache_dir=tmp_path / "cache"
            )
    assert result.cache_key is None and not result.cache_hit
    assert not list((tmp_path / "cache").rglob("*.json"))


def test_parallel_reader_parameters_publish_separate_complete_payloads(tmp_path):
    path = write_pdf(tmp_path / "parallel.pdf")
    cache = tmp_path / "cache"

    def load(full):
        return load_data_with_parse_cache(
            PDFReader(return_full_document=full),
            path,
            cache_dir=cache,
            extra_info={"owner": str(full)},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(load, [False, True]))
    assert [len(result.documents) for result in results] == [3, 1]
    assert len({result.cache_key for result in results}) == 2
    for full, expected_length in [(False, 3), (True, 1)]:
        result = load(full)
        assert result.cache_hit and len(result.documents) == expected_length
        assert all(doc.metadata["owner"] == str(full) for doc in result.documents)
    payloads = [json.loads(file.read_text()) for file in cache.rglob("*.json")]
    assert sorted(len(payload["documents"]) for payload in payloads) == [1, 3]
    assert not list(cache.rglob("*.tmp"))


def test_pdf_parser_failure_publishes_no_partial_cache_payload(tmp_path):
    path = tmp_path / "invalid.pdf"
    path.write_bytes(b"not a PDF")
    with pytest.raises(RetryError):
        load_data_with_parse_cache(
            AutoReader("PDFReader"), path, cache_dir=tmp_path / "cache"
        )
    assert not list((tmp_path / "cache").rglob("*.json"))


@pytest.mark.parametrize("wrapper", [False, True])
def test_actual_pdf_reader_parameters_invalidate_even_with_caller_override(
    tmp_path, wrapper
):
    path = write_pdf(tmp_path / "params.pdf")
    reader = AutoReader("PDFReader") if wrapper else PDFReader()
    actual = reader._reader if wrapper else reader
    first = load_data_with_parse_cache(reader, path, cache_dir=tmp_path / "cache")
    assert len(first.documents) == 3
    actual.return_full_document = True
    second = load_data_with_parse_cache(reader, path, cache_dir=tmp_path / "cache")
    assert not second.cache_hit
    assert len(second.documents) == 1
    policy = {"return_full_document": False, "parser_identity": "old"}
    full_key = build_parse_cache_key(reader, path, reader_policy=policy)
    actual.return_full_document = False
    assert build_parse_cache_key(reader, path, reader_policy=policy) != full_key


@pytest.mark.parametrize(
    "factory", [PDFReader, lambda: AutoReader("PDFReader"), PDFThumbnailReader]
)
def test_dependency_identity_is_automatic_before_lookup(tmp_path, factory):
    path = write_pdf(tmp_path / "versions.pdf")
    reader = factory()
    key = build_parse_cache_key(reader, path)
    real_version = importlib.metadata.version
    with patch(
        "importlib.metadata.version",
        side_effect=lambda name: "different" if name == "pypdf" else real_version(name),
    ):
        assert build_parse_cache_key(reader, path) != key
    with patch(
        "importlib.metadata.version",
        side_effect=lambda name: "different"
        if name == "unrelated-package"
        else real_version(name),
    ):
        assert build_parse_cache_key(reader, path) == key


def test_missing_pdf_distribution_metadata_bypasses_with_diagnostic(tmp_path):
    path = write_pdf(tmp_path / "missing.pdf")
    reader = AutoReader("PDFReader")
    real_version = importlib.metadata.version

    def missing(name):
        if name == "pypdf":
            raise importlib.metadata.PackageNotFoundError(name)
        return real_version(name)

    with patch("importlib.metadata.version", side_effect=missing):
        with pytest.warns(RuntimeWarning, match="PDF parse cache bypass"):
            first = load_data_with_parse_cache(
                reader, path, cache_dir=tmp_path / "cache"
            )
        with pytest.warns(RuntimeWarning, match="PDF parse cache bypass"):
            second = load_data_with_parse_cache(
                reader, path, cache_dir=tmp_path / "cache"
            )
    assert not first.cache_hit and not second.cache_hit
    assert first.cache_key is second.cache_key is None
    assert first.stats == {"hits": 0, "misses": 0, "writes": 0}
    assert not list((tmp_path / "cache").rglob("*.json"))
