from __future__ import annotations

import argparse
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sidecar.application import configure_desktop_data_root

GATE2_SMOKE_FILE_ID = "gate2-smoke-file"
GATE2_SMOKE_SESSION_ID = "gate2-smoke-session"
GATE2_SMOKE_TIMESTAMP = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
GATE3_FORMAT_INPUT_NAMES = (
    "gate3-format.md",
    "gate3-format.csv",
    "gate3-format.html",
    "gate3-format.mhtml",
    "gate3-format.zip",
)


def _get_or_create_file_index_id(engine: Any, flowsettings: Any) -> int:
    from ktem.index.models import Index
    from sqlmodel import Session, select

    definitions = [
        definition
        for definition in flowsettings.KH_INDICES
        if str(definition.get("index_type", "")).endswith("FileIndex")
    ]
    if len(definitions) != 1:
        raise RuntimeError("Gate 2 smoke fixture requires one configured FileIndex")
    definition = definitions[0]

    with Session(engine) as session:
        indices = list(session.exec(select(Index)).all())
        if len(indices) > 1 or (
            indices and not str(indices[0].index_type).endswith("FileIndex")
        ):
            raise RuntimeError("Gate 2 smoke fixture requires a dedicated data root")
        if indices:
            index = indices[0]
        else:
            index = Index(
                name=str(definition["name"]),
                config=dict(definition["config"]),
                index_type=str(definition["index_type"]),
            )
            session.add(index)
            session.commit()
            session.refresh(index)
        if index.id is None:
            raise RuntimeError("Gate 2 smoke FileIndex has no database ID")
        return index.id


def _create_source_table(engine: Any, index_id: int) -> Any:
    from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table

    metadata = MetaData()
    source_table = Table(
        f"index__{index_id}__source",
        metadata,
        Column("id", String, primary_key=True),
        Column("name", String, nullable=False),
        Column("path", String, nullable=False),
        Column("size", Integer, nullable=False),
        Column("date_created", DateTime(timezone=True), nullable=False),
        Column("user", String, nullable=False),
        Column("note", JSON, nullable=False),
    )
    Table(
        f"index__{index_id}__index",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("source_id", String),
        Column("target_id", String),
        Column("relation_type", String),
        Column("user", String, nullable=False, default=""),
    )
    metadata.create_all(engine)
    return source_table


def _seed_file_record(
    engine: Any,
    source_table: Any,
    file_path: Path,
    stored_path: Path,
) -> None:
    from sqlalchemy import delete as sql_delete
    from sqlalchemy import select as sql_select

    with engine.begin() as connection:
        file_ids = set(connection.execute(sql_select(source_table.c.id)).scalars())
        if file_ids - {GATE2_SMOKE_FILE_ID}:
            raise RuntimeError("Gate 2 smoke fixture requires a dedicated data root")
        connection.execute(
            sql_delete(source_table).where(source_table.c.id == GATE2_SMOKE_FILE_ID)
        )
        connection.execute(
            source_table.insert().values(
                id=GATE2_SMOKE_FILE_ID,
                name=file_path.name,
                path=str(stored_path),
                size=file_path.stat().st_size,
                date_created=GATE2_SMOKE_TIMESTAMP,
                user="default",
                note={"tokens": 7, "loader": "TextReader"},
            )
        )


def _seed_conversation(engine: Any, conversation_model: Any) -> None:
    from sqlmodel import Session, select

    with Session(engine) as session:
        conversation_ids = {
            row.id for row in session.exec(select(conversation_model)).all()
        }
        if conversation_ids - {GATE2_SMOKE_SESSION_ID}:
            raise RuntimeError("Gate 2 smoke fixture requires a dedicated data root")
        session.merge(
            conversation_model(
                id=GATE2_SMOKE_SESSION_ID,
                name="Gate 2 smoke session",
                user="default",
                is_public=False,
                data_source={
                    "origin": "desktop-gate2-smoke",
                    "graph_source_ids": [GATE2_SMOKE_FILE_ID],
                    "messages": [
                        {"role": "user", "content": "What is this fixture?"},
                        {
                            "role": "assistant",
                            "content": "A packaged Desktop smoke record.",
                        },
                    ],
                },
                date_created=GATE2_SMOKE_TIMESTAMP,
                date_updated=GATE2_SMOKE_TIMESTAMP,
            )
        )
        session.commit()


def _seed_gate3_format_inputs(data_root: Path) -> None:
    input_root = data_root / "tmp"
    input_root.mkdir(parents=True, exist_ok=True)
    (input_root / "gate3-format.md").write_text(
        "# Gate 3 Markdown\n\nMARA format matrix fixture.\n",
        encoding="utf-8",
    )
    (input_root / "gate3-format.csv").write_text(
        "metric,value\nindexed_files,6\n",
        encoding="utf-8",
    )
    (input_root / "gate3-format.html").write_text(
        "<html><body><h1>Gate 3 HTML</h1><p>MARA fixture.</p></body></html>\n",
        encoding="utf-8",
    )
    (input_root / "gate3-format.mhtml").write_text(
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/related; boundary="mara-gate3"\n\n'
        "--mara-gate3\n"
        "Content-Type: text/html; charset=utf-8\n"
        "Content-Transfer-Encoding: 8bit\n\n"
        "<html><head><title>Gate 3 MHTML</title></head>"
        "<body><p>MARA fixture.</p></body></html>\n"
        "--mara-gate3--\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(input_root / "gate3-format.zip", "w") as archive:
        archive.writestr(
            "gate3-zip-note.md",
            "# Gate 3 ZIP\n\nSafely extracted MARA fixture.\n",
        )


def seed_smoke_fixture(data_root: Path) -> None:
    resolved_root = data_root.expanduser().resolve()
    configure_desktop_data_root(resolved_root)

    from ktem.db.models import Conversation, engine
    from theflow.settings import settings as flowsettings

    index_id = _get_or_create_file_index_id(engine, flowsettings)
    source_table = _create_source_table(engine, index_id)
    storage_root = (
        resolved_root
        / "state"
        / "ktem_app_data"
        / "user_data"
        / "files"
        / f"index_{index_id}"
    )
    stored_path = Path("gate2-smoke.txt")
    file_path = storage_root / stored_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "MARA Desktop Gate 2 deterministic smoke fixture.\n",
        encoding="utf-8",
    )
    _seed_file_record(engine, source_table, file_path, stored_path)
    _seed_conversation(engine, Conversation)
    _seed_gate3_format_inputs(resolved_root)


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
