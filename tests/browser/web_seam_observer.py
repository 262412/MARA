"""Read files produced by real Studio callbacks in the harness-owned runtime."""

import hashlib
from pathlib import Path


def studio_exports(conversations, root):
    root = Path(root).resolve()
    exports = []
    for row in conversations:
        notebook = (row.data_source or {}).get("mara_notebook", {})
        for artifact in notebook.get("artifacts", []):
            for record in artifact.get("exports", []):
                path = Path(record["path"]).resolve()
                assert path.is_relative_to(root), path
                content = path.read_bytes()
                exports.append(
                    {
                        "conversation_id": row.id,
                        "artifact_id": artifact["artifact_id"],
                        "path": str(path),
                        "bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "text": content.decode("utf-8")
                        if path.suffix == ".md"
                        else None,
                    }
                )
    return exports
