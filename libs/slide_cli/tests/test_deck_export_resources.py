"""Only a conversion's new output and its owned temporary files may change."""

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest
from slide_cli import deck


def test_same_stem_concurrent_exports_have_distinct_workspaces(tmp_path, monkeypatch):
    sources = [tmp_path / name / "same.pptx" for name in ("a", "b")]
    for source in sources:
        source.parent.mkdir()
        source.write_bytes(source.parent.name.encode())
    barrier = Barrier(2)
    workspaces = []

    def convert(command, **kwargs):
        workspace = Path(command[command.index("--outdir") + 1])
        workspaces.append(workspace)
        barrier.wait(timeout=5)
        (workspace / "same.pdf").write_bytes(Path(command[-1]).read_bytes())
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(deck.subprocess, "run", convert)

    def export(source):
        return deck.export_deck_pdf(
            source,
            output_path=tmp_path / f"{source.parent.name}.pdf",
            soffice_path="owned",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(export, sources))
    assert [path.read_bytes() for path in outputs] == [b"a", b"b"]
    assert len(set(workspaces)) == 2
    assert all(not path.exists() for path in workspaces)


@pytest.mark.parametrize("stage", ["convert", "publish", "cleanup", "both"])
def test_publication_and_cleanup_failure_report_committed_state(
    tmp_path, monkeypatch, caplog, stage
):
    source, target = tmp_path / "owned.pptx", tmp_path / "owned.pdf"
    source.write_bytes(b"source")
    target.write_bytes(b"old")
    workspaces = []
    primary = subprocess.TimeoutExpired("owned", 3)
    original_replace = Path.replace
    original_cleanup = deck.shutil.rmtree

    def convert(command, **kwargs):
        workspace = Path(command[command.index("--outdir") + 1])
        workspaces.append(workspace)
        (workspace / "owned.pdf").write_bytes(b"new")
        if stage in {"convert", "both"}:
            raise primary
        return SimpleNamespace(returncode=0)

    def publish(path, destination):
        if stage == "publish":
            raise PermissionError("owned publish failure")
        return original_replace(path, destination)

    def cleanup(path):
        if stage in {"cleanup", "both"}:
            raise PermissionError("owned cleanup failure")
        original_cleanup(path)

    with monkeypatch.context() as patch:
        patch.setattr(deck.subprocess, "run", convert)
        patch.setattr(Path, "replace", publish)
        patch.setattr(deck.shutil, "rmtree", cleanup)
        with pytest.raises((subprocess.TimeoutExpired, PermissionError)) as caught:
            deck.export_deck_pdf(source, soffice_path="owned")
    assert target.read_bytes() == (b"new" if stage == "cleanup" else b"old")
    if stage in {"convert", "both"}:
        assert caught.value is primary
    if stage == "both":
        assert "owned cleanup failure" in caplog.text
    assert len(workspaces) == 1
    assert workspaces[0].exists() == (stage in {"cleanup", "both"})
    if workspaces[0].exists():
        original_cleanup(workspaces[0])
