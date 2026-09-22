"""Verify installed modules and preview assets without making model requests."""

import importlib
import importlib.metadata
import os
import sys
from pathlib import Path

prefix = Path(sys.prefix).resolve()
for name in ("kotaemon", "ktem", "mara-research-cli", "mara-app"):
    location = Path(importlib.metadata.distribution(name).locate_file("")).resolve()
    if not location.is_relative_to(prefix):
        raise RuntimeError(f"{name} was loaded outside the isolated environment")
for name in ("slide_cli.cli", "ktem.index.file.pipelines", "ktem_contracts"):
    module = importlib.import_module(name)
    if module.__file__ is None or not Path(module.__file__).resolve().is_relative_to(
        prefix
    ):
        raise RuntimeError(f"{name} was imported from an external checkout")

from ktem.runtime_bootstrap import get_runtime_paths  # noqa: E402

expected = Path(os.environ["MARA_APP_HOME"]).resolve()
paths = get_runtime_paths()
if paths.data_dir != expected / "data":
    raise RuntimeError("Application data is not isolated in the reviewer directory")
viewer = expected / "data/assets/pdfjs/6.1.200/web/viewer.html"
if not viewer.is_file():
    raise RuntimeError(f"Bundled PDF preview resource was not initialized: {viewer}")
print("Installed modules, isolated data paths, and PDF preview assets: OK")
