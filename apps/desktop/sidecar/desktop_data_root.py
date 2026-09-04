from __future__ import annotations

import os
from pathlib import Path

DESKTOP_DATA_DIRECTORIES = (
    "state",
    "documents",
    "previews",
    "cache",
    "logs",
    "backups",
    "tmp",
)


def configure_desktop_data_root(data_root: Path) -> Path:
    expanded_root = data_root.expanduser()
    if not expanded_root.is_absolute():
        raise ValueError("Desktop data root must be absolute")
    resolved_root = expanded_root.resolve()

    os.environ["MARA_DESKTOP_DATA_DIR"] = str(resolved_root)
    os.environ["THEFLOW_SETTINGS_MODULE"] = "ktem.default_flowsettings"
    os.environ["KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED"] = "1"

    for directory in DESKTOP_DATA_DIRECTORIES:
        (resolved_root / directory).mkdir(parents=True, exist_ok=True)
    app_data_dir = resolved_root / "state" / "ktem_app_data"
    app_data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["KH_APP_DATA_DIR"] = str(app_data_dir)
    os.environ["KH_OFFICE_TO_PDF_INDEXING"] = "false"
    return app_data_dir
