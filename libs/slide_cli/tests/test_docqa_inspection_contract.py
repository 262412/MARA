"""Freeze lightweight inspection's SQL, projection and diagnostic contracts."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from ktem.db.models import Conversation
from ktem.index.models import Index
from slide_cli import docqa_runtime as inspection
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine
from theflow.settings import settings


@pytest.fixture
def inspection_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'inspection.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("ktem.db.models.engine", engine)
    for name, value in {
        "KH_FEATURE_USER_MANAGEMENT": False,
        "KH_INDICES": [{"name": "Configured", "index_type": "example.FileIndex"}],
        "KH_LLMS": {"configured": {"default": True, "spec": {}}},
        "KH_EMBEDDINGS": {"embedding": {"spec": {"api_key": "your-key"}}},
    }.items():
        monkeypatch.setattr(settings, name, value)
    _seed_sessions(engine)
    _seed_files(engine, tmp_path)
    yield engine
    engine.dispose()


def _seed_sessions(engine):
    with Session(engine) as session:
        session.add(
            Index(
                id=701,
                name="Persisted",
                index_type="example.FileIndex",
                config={"private": True},
            )
        )
        for identifier, owner, public, day, source in (
            (
                "own",
                "default",
                False,
                2,
                {
                    "messages": [["q", "a"]],
                    "graph_source_ids": [" x ", "x"],
                    "origin": "cli",
                },
            ),
            (
                "public",
                "other",
                True,
                3,
                {"selected": {"1": ["select", ["a", "a", "b"]]}},
            ),
            ("private", "other", False, 4, {}),
        ):
            session.add(
                Conversation(
                    id=identifier,
                    user=owner,
                    name=identifier,
                    is_public=public,
                    data_source=source,
                    date_created=datetime(2026, 1, day),
                    date_updated=datetime(2026, 2, day),
                )
            )
        session.commit()


def _seed_files(engine, tmp_path):
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE index__701__source "
                "(id TEXT, name TEXT, size INTEGER, path TEXT, "
                "date_created TEXT, note TEXT, user TEXT)"
            )
        )
        for identifier, owner, day in (
            ("old", "default", 1),
            ("new", "default", 3),
            ("other", "other", 4),
        ):
            connection.execute(
                text(
                    "INSERT INTO index__701__source VALUES "
                    "(:id,:name,12,:path,:date,:note,:owner)"
                ),
                {
                    "id": identifier,
                    "name": identifier + "中文.txt",
                    "path": str(tmp_path / identifier),
                    "date": f"2026-01-0{day}",
                    "note": json.dumps({"tokens": "7", "loader": "text"}),
                    "owner": owner,
                },
            )
        connection.execute(
            text("CREATE TABLE llm_table " '(name TEXT, spec TEXT, "default" INTEGER)')
        )
        connection.execute(
            text("INSERT INTO llm_table VALUES (:name,:spec,1)"),
            {"name": "persisted", "spec": '{"api_key":"YOUR_KEY"}'},
        )


def test_records_order_fields_types_and_detachment(inspection_db):
    files = inspection.collect_docqa_file_records()
    assert [row["file_id"] for row in files] == ["new", "old"]
    assert list(files[0]) == [
        "file_id",
        "name",
        "size",
        "tokens",
        "loader",
        "path",
        "date_created",
    ]
    assert files[0] == {
        "file_id": "new",
        "name": "new中文.txt",
        "size": 12,
        "tokens": 7,
        "loader": "text",
        "path": files[0]["path"],
        "date_created": "2026-01-03",
    }
    sessions = inspection.collect_docqa_session_summaries()
    assert [row["conversation_id"] for row in sessions] == ["public", "own"]
    assert list(sessions[0]) == [
        "conversation_id",
        "name",
        "message_count",
        "graph_source_count",
        "origin",
        "is_public",
        "date_created",
        "date_updated",
    ]
    assert sessions[1] == {
        "conversation_id": "own",
        "name": "own",
        "message_count": 1,
        "graph_source_count": 2,
        "origin": "cli",
        "is_public": False,
        "date_created": "2026-01-02T00:00:00",
        "date_updated": "2026-02-02T00:00:00",
    }
    assert sessions[0]["graph_source_count"] == 2
    files[0]["name"] = sessions[0]["name"] = "changed"
    assert inspection.collect_docqa_file_records()[0]["name"] == "new中文.txt"
    assert inspection.collect_docqa_session_summaries()[0]["name"] == "public"


def test_doctor_persisted_defaults_and_diagnostic_order(inspection_db):
    payload = inspection.collect_docqa_doctor_payload()
    assert list(payload) == [
        "ok",
        "app_name",
        "default_user_id",
        "index_name",
        "index_id",
        "llm_default",
        "embedding_default",
        "file_count",
        "session_count",
        "graph_cache_dir",
        "issues",
        "warnings",
    ]
    assert payload["ok"] is True
    assert (payload["default_user_id"], payload["index_name"], payload["index_id"]) == (
        "default",
        "Persisted",
        701,
    )
    assert (
        payload["llm_default"],
        payload["embedding_default"],
        payload["file_count"],
        payload["session_count"],
    ) == ("persisted", "embedding", 2, 2)
    assert payload["issues"] == []
    assert payload["warnings"] == [
        "Default LLM 'persisted' appears to use placeholder credentials.",
        "Default embedding model 'embedding' appears to use placeholder credentials.",
    ]


def test_missing_index_table_and_database_error_timing(inspection_db):
    with inspection_db.begin() as connection:
        connection.execute(text("DROP TABLE index__701__source"))
    assert inspection.collect_docqa_file_records() == []
    payload = inspection.collect_docqa_doctor_payload()
    assert payload["ok"] is False
    assert payload["issues"] == ["Indexed file table 'index__701__source' is missing."]
    with inspection_db.begin() as connection:
        connection.execute(text("DROP TABLE conversation"))
    count, issues = inspection._count_saved_sessions(
        inspection_db, Conversation, "default"
    )
    assert count == 0 and issues[0].startswith("Unable to read saved sessions:")
    with pytest.raises(Exception, match="no such table"):
        inspection.collect_docqa_session_summaries()


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, []),
        ({"graph_source_ids": [0, False, " ", " x ", "x"]}, [" x ", "x"]),
        ({"graph_source_ids": 0}, ["0"]),
        (
            {"selected": {"x": ["all", [" a ", "a", {}, ["deep"], None], "b"]}},
            ["a", "b"],
        ),
    ],
)
def test_graph_legacy_fallback_preserves_its_own_normalization(value, expected):
    before = json.dumps(value)
    assert inspection._extract_graph_source_ids(value) == expected
    assert json.dumps(value) == before


def test_json_copy_and_date_failure_contract():
    nested: dict[str, list[str]] = {"items": []}
    copied = inspection._load_json_dict(nested)
    assert (
        copied == nested and copied is not nested and copied["items"] is nested["items"]
    )
    assert inspection._load_json_dict("[]") == inspection._load_json_dict("{bad") == {}
    assert inspection._serialize_value(datetime(2026, 1, 2)) == "2026-01-02T00:00:00"

    def fail():
        raise ValueError("bad date")

    broken = SimpleNamespace(isoformat=fail)
    assert inspection._serialize_value(broken) is broken


def test_model_fallback_missing_configs_and_private_index_identity(inspection_db):
    issues: list[str] = []
    warnings: list[str] = []
    assert (
        inspection._pick_default_model_name(
            {}, label="LLM", issues=issues, warnings=warnings
        )
        == ""
    )
    assert issues == ["No configured default LLM is available."]
    assert (
        inspection._pick_default_model_name(
            {"first": {}, "second": {}}, label="LLM", issues=[], warnings=[]
        )
        == "first"
    )
    assert inspection._count_indexed_files(
        inspection_db, index_id=701, private_index=True, default_user_id=""
    ) == (0, ["Cannot inspect indexed files without a default DocQA user."])
    assert inspection._count_indexed_files(
        inspection_db, index_id=701, private_index=False, default_user_id=""
    ) == (3, [])
