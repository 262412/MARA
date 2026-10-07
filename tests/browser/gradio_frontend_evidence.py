"""Identify the installed frontend used by the owned Gradio browser fixture."""

import hashlib
from pathlib import Path


def installed_frontend():
    import gradio

    assert gradio.__version__ == "6.29.1"
    bundle = (
        Path(gradio.__file__).parent / "templates/frontend/assets/Blocks-BC25XO0Z.js"
    )
    source_map = bundle.with_suffix(".js.map")
    return {
        "version": gradio.__version__,
        "path": str(bundle),
        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "map_sha256": hashlib.sha256(source_map.read_bytes()).hexdigest()
        if source_map.is_file()
        else None,
    }
