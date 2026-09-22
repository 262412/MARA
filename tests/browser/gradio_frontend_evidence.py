"""Identify the installed frontend used by the owned Gradio browser fixture."""

import hashlib
from pathlib import Path


def installed_frontend():
    import gradio

    assert gradio.__version__ == "4.39.0"
    bundle = (
        Path(gradio.__file__).parent / "templates/frontend/assets/Blocks-BPGBf-rO.js"
    )
    return {
        "version": gradio.__version__,
        "path": str(bundle),
        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "map_sha256": hashlib.sha256(
            bundle.with_suffix(".js.map").read_bytes()
        ).hexdigest(),
    }
