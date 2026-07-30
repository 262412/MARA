from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from sidecar.application import configure_desktop_data_root

GATE2_SMOKE_FILE_ID = "gate2-smoke-file"
GATE2_SMOKE_SESSION_ID = "gate2-smoke-session"
GATE2_SMOKE_TIMESTAMP = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def seed_smoke_fixture(data_root: Path) -> None:
    resolved_root = data_root.expanduser().resolve()
    configure_desktop_data_root(resolved_root)

    from ktem.db.models import Conversation, engine
    from ktem.index.manager import IndexManager
    from sqlmodel import Session

    manager = IndexManager(SimpleNamespace())
    manager.on_application_startup()
    if len(manager.indices) != 1:
        raise RuntimeError("Gate 2 smoke fixture requires exactly one FileIndex")

    file_path = resolved_root / "documents" / "gate2-smoke.txt"
    file_path.write_text(
        "MARA Desktop Gate 2 deterministic smoke fixture.\n",
        encoding="utf-8",
    )
    source_model = manager.indices[0]._resources["Source"]
    source = source_model(
        id=GATE2_SMOKE_FILE_ID,
        name=file_path.name,
        path=str(file_path),
        size=file_path.stat().st_size,
        date_created=GATE2_SMOKE_TIMESTAMP,
        user="default",
        note={"tokens": 7, "loader": "TextReader"},
    )
    conversation = Conversation(
        id=GATE2_SMOKE_SESSION_ID,
        name="Gate 2 smoke session",
        user="default",
        is_public=False,
        data_source={
            "origin": "desktop-gate2-smoke",
            "graph_source_ids": [GATE2_SMOKE_FILE_ID],
            "messages": [
                {"role": "user", "content": "What is this fixture?"},
                {"role": "assistant", "content": "A packaged Desktop smoke record."},
            ],
        },
        date_created=GATE2_SMOKE_TIMESTAMP,
        date_updated=GATE2_SMOKE_TIMESTAMP,
    )

    with Session(engine) as session:
        session.merge(source)
        session.merge(conversation)
        session.commit()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed deterministic Gate 2 Desktop smoke data."
    )
    parser.add_argument("--data-root", required=True, type=Path)
    arguments = parser.parse_args()
    seed_smoke_fixture(arguments.data_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
