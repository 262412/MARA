"""The installed Gradio component must load without writing package files."""

import ast
import sys
from pathlib import Path
from types import ModuleType

import gradio as gr
from gradio.data_classes import FileData


def test_download_component_loads_from_read_only_installation(tmp_path, monkeypatch):
    source = Path(__file__).parents[1] / "ktem/index/file/download_http.py"
    installed = tmp_path / source.name
    installed.write_bytes(source.read_bytes())
    interface = source.with_suffix(".pyi")
    if interface.exists():
        installed.with_suffix(".pyi").write_bytes(interface.read_bytes())

    original_open = Path.open

    def read_only_open(path, mode="r", *args, **kwargs):
        if path.parent == tmp_path and any(flag in mode for flag in "wax+"):
            raise PermissionError("installed package is read-only")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", read_only_open)
    module = ModuleType("owned_readonly_download_component")
    module.__file__ = str(installed)
    module.__dict__.update(gr=gr, FileData=FileData)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    definition = next(
        node
        for node in ast.parse(installed.read_text(encoding="utf-8")).body
        if isinstance(node, ast.ClassDef) and node.name == "DownloadButton"
    )
    tree = ast.Module(body=[definition], type_ignores=[])
    exec(compile(tree, str(installed), "exec"), module.__dict__)
    button = module.__dict__["DownloadButton"](render=False)
    result = button.postprocess("https://example.test/mara-download/owned.zip")
    assert result.path == result.url == "https://example.test/mara-download/owned.zip"
    assert button.get_block_name() == "downloadbutton"
