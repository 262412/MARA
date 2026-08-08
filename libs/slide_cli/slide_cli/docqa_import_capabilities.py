from __future__ import annotations

import re
from typing import Any

_SUPPORTED_EXTENSION_PATTERN = re.compile(r"^\.[a-z0-9]{1,16}$")


def select_file_index_config(flowsettings: Any, rows: list[Any]) -> dict[str, Any]:
    for row in rows:
        if str(getattr(row, "index_type", "")).endswith("FileIndex"):
            return dict(getattr(row, "config", {}) or {})

    for definition in getattr(flowsettings, "KH_INDICES", []) or []:
        if str((definition or {}).get("index_type", "")).endswith("FileIndex"):
            return dict((definition or {}).get("config", {}) or {})
    return {}


def normalize_supported_extensions(value: Any) -> list[str]:
    extensions: list[str] = []
    for item in str(value or "").split(","):
        extension = item.strip().lower()
        if (
            _SUPPORTED_EXTENSION_PATTERN.fullmatch(extension)
            and extension not in extensions
        ):
            extensions.append(extension)
    return extensions


def collect_docqa_import_capabilities() -> dict[str, list[str]]:
    from ktem.runtime_bootstrap import bootstrap_runtime_settings

    bootstrap_runtime_settings()

    from ktem.db.models import engine
    from ktem.index.models import Index
    from sqlmodel import Session, select
    from theflow.settings import settings as flowsettings

    with Session(engine) as session:
        rows = list(session.exec(select(Index)).all())
    config = select_file_index_config(flowsettings, rows)
    extensions = normalize_supported_extensions(config.get("supported_file_types", ""))
    if not extensions:
        raise RuntimeError("No supported DocQA file types are configured.")
    return {"supported_extensions": extensions}
