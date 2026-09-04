from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import kotaemon.artifact_namespace as artifact_module
from kotaemon.artifact_namespace import ArtifactNamespaceError, load_manifest_artifacts

FILE_ID = "file-owner"
GENERATION = "generation-a"


@pytest.fixture
def roots(tmp_path):
    result = SimpleNamespace(
        chunks=tmp_path / "chunks",
        markdown=tmp_path / "markdown",
        zip=tmp_path / "zip",
    )
    for root in vars(result).values():
        root.mkdir()
    return result


def _manifest_path(roots) -> Path:
    path = roots.zip / "manifests" / "v1" / FILE_ID / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _leaf(roots, name: str = "report.md", *, size: int | None = None) -> Path:
    path = roots.markdown / FILE_ID / GENERATION / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if size is None:
        path.write_text("OWNER", encoding="utf-8")
    else:
        with path.open("wb") as output:
            output.truncate(size)
    return path


def _entry(relative_path: str | None = None) -> dict[str, str]:
    return {
        "kind": "markdown",
        "relative_path": relative_path or f"{FILE_ID}/{GENERATION}/report.md",
    }


def _record(entries=None, **overrides):
    record = {
        "version": 1,
        "file_id": FILE_ID,
        "entries": [_entry()] if entries is None else entries,
    }
    record.update(overrides)
    return record


def _write_record(roots, record) -> None:
    _manifest_path(roots).write_text(json.dumps(record), encoding="utf-8")


def _load(roots):
    return load_manifest_artifacts(
        FILE_ID,
        {"chunks": roots.chunks, "markdown": roots.markdown},
        roots.zip,
    )


def test_manifest_rejects_oversized_valid_json_before_decoding(roots):
    _leaf(roots)
    payload = json.dumps(_record()).encode("utf-8") + b" " * (1024 * 1024)
    _manifest_path(roots).write_bytes(payload)

    with pytest.raises(ArtifactNamespaceError, match="manifest"):
        _load(roots)


def test_manifest_rejects_entry_count_before_entry_resolution(roots, monkeypatch):
    _leaf(roots)
    entries = [
        _entry(f"{FILE_ID}/{GENERATION}/report-{index}.md") for index in range(2_001)
    ]
    _write_record(roots, _record(entries))

    def fail_resolve(*_args, **_kwargs):
        pytest.fail("manifest entries must be bounded before resolution")

    monkeypatch.setattr(artifact_module, "_resolve_manifest_entry", fail_resolve)

    with pytest.raises(ArtifactNamespaceError, match="entries"):
        _load(roots)


def test_manifest_rejects_long_relative_path(roots):
    parts = [f"segment-{index}-" + "x" * 205 for index in range(5)]
    relative = "/".join((FILE_ID, GENERATION, *parts, "report.md"))
    path = roots.markdown.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True)
    path.write_text("OWNER", encoding="utf-8")
    _write_record(roots, _record([_entry(relative)]))

    with pytest.raises(ArtifactNamespaceError, match="path"):
        _load(roots)


def test_manifest_rejects_sparse_total_artifact_size(roots):
    _leaf(roots, size=2 * 1024 * 1024 * 1024 + 1)
    _write_record(roots, _record())

    with pytest.raises(ArtifactNamespaceError, match="size"):
        _load(roots)


def test_manifest_rejects_boolean_version(roots):
    _leaf(roots)
    _write_record(roots, _record(version=True))

    with pytest.raises(ArtifactNamespaceError, match="version"):
        _load(roots)


@pytest.mark.parametrize(
    "relative",
    [
        f"{FILE_ID}/{GENERATION}/./report.md",
        f"{FILE_ID}/{GENERATION}//report.md",
    ],
)
def test_manifest_rejects_explicit_empty_or_dot_path_segments(roots, relative):
    _leaf(roots)
    _write_record(roots, _record([_entry(relative)]))

    with pytest.raises(ArtifactNamespaceError, match="path"):
        _load(roots)


def test_manifest_wraps_deep_json_recursion(roots):
    nested = "[" * 1_100 + "0" + "]" * 1_100
    _manifest_path(roots).write_text(
        '{"version":1,"file_id":"file-owner","entries":' + nested + "}",
        encoding="utf-8",
    )

    with pytest.raises(ArtifactNamespaceError, match="manifest"):
        _load(roots)


def test_manifest_wraps_unicode_decode_failure(roots):
    _manifest_path(roots).write_bytes(b"\xff\xfe\xfd")

    with pytest.raises(ArtifactNamespaceError, match="manifest"):
        _load(roots)


def test_manifest_rejects_duplicate_json_keys(roots):
    _leaf(roots)
    _manifest_path(roots).write_text(
        "{"
        '"version":1,"version":1,"file_id":"file-owner",'
        '"entries":[{"kind":"markdown",'
        '"relative_path":"file-owner/generation-a/report.md"}]}',
        encoding="utf-8",
    )

    with pytest.raises(ArtifactNamespaceError, match="duplicate"):
        _load(roots)


def test_manifest_rejects_empty_entries(roots):
    _write_record(roots, _record([]))

    with pytest.raises(ArtifactNamespaceError, match="entries"):
        _load(roots)


def test_manifest_rejects_portable_duplicate_archive_names(roots):
    first = _leaf(roots, "Report.md")
    second = first.with_name("report.md")
    second.write_text("OTHER", encoding="utf-8")
    _write_record(
        roots,
        _record(
            [
                _entry(f"{FILE_ID}/{GENERATION}/{first.name}"),
                _entry(f"{FILE_ID}/{GENERATION}/{second.name}"),
            ]
        ),
    )

    with pytest.raises(ArtifactNamespaceError, match="Duplicate"):
        _load(roots)


def test_manifest_rejects_paths_deeper_than_generation_leaf_layout(roots):
    nested = roots.markdown / FILE_ID / GENERATION / "nested" / "report.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("OWNER", encoding="utf-8")
    _write_record(
        roots,
        _record([_entry(f"{FILE_ID}/{GENERATION}/nested/report.md")]),
    )

    with pytest.raises(ArtifactNamespaceError, match="path"):
        _load(roots)


@pytest.mark.parametrize(
    "leaf_name",
    ["CON.md", "report:.md", "report\x01.md", "report.md ", "report\x00.md"],
)
def test_manifest_rejects_nonportable_leaf_names(roots, leaf_name):
    _write_record(
        roots,
        _record([_entry(f"{FILE_ID}/{GENERATION}/{leaf_name}")]),
    )

    with pytest.raises(ArtifactNamespaceError, match="path"):
        _load(roots)


@pytest.mark.parametrize("invalid", ["version", "file_id", "absolute", "directory"])
def test_manifest_direct_identity_and_type_rejections(roots, invalid):
    leaf = _leaf(roots)
    record = _record()
    if invalid == "version":
        record["version"] = 2
    elif invalid == "file_id":
        record["file_id"] = "file-victim"
    elif invalid == "absolute":
        record["entries"] = [_entry(str(leaf))]
    else:
        record["entries"] = [_entry(f"{FILE_ID}/{GENERATION}")]
    _write_record(roots, record)

    with pytest.raises(ArtifactNamespaceError):
        _load(roots)
