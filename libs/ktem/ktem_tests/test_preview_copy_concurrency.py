"""Concurrent browser previews publish the same immutable PDF only once."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

from ktem.pages.chat import page_preview_runtime as preview


def test_concurrent_preview_does_not_replace_an_already_served_copy(
    tmp_path, monkeypatch
):
    source = tmp_path / "owned.pdf"
    source.write_bytes(b"owned PDF bytes")
    monkeypatch.setenv("GRADIO_TEMP_DIR", str(tmp_path / "gradio"))
    ready = Barrier(2)
    copied = Event()
    signature = preview.get_file_signature
    copy = preview.shutil.copyfile
    replace = preview.os.replace
    copies = []

    def concurrent_signature(path):
        value = signature(path)
        ready.wait(timeout=3)
        return value

    def slow_first_copy(src, dst):
        copies.append(dst)
        if len(copies) == 1:
            copied.wait(timeout=0.2)
        result = copy(src, dst)
        copied.set()
        return result

    def publish(src, dst):
        if Path(dst).exists():
            raise PermissionError("the browser is already serving this PDF")
        return replace(src, dst)

    monkeypatch.setattr(preview, "get_file_signature", concurrent_signature)
    monkeypatch.setattr(preview.shutil, "copyfile", slow_first_copy)
    monkeypatch.setattr(preview.os, "replace", publish)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(preview.ensure_pdf_preview_copy, str(source), source.name)
            for _ in range(2)
        ]
        paths = [future.result(timeout=5) for future in futures]
    assert paths[0] == paths[1]
    assert Path(paths[0]).read_bytes() == source.read_bytes()
    assert len(copies) == 1
    assert not list((tmp_path / "gradio" / "pdf_previews").glob("*.tmp"))
