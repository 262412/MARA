from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from ktem.index.file._group_service import FileGroupService, GroupServiceError
from ktem.index.file._indexing_service import FileIndexingService
from sqlalchemy import JSON, Column, DateTime, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.mutable import MutableDict


def _drain(generator):
    values = []
    while True:
        try:
            values.append(next(generator))
        except StopIteration as exc:
            return values, exc.value


class _Route:
    def __init__(self, existing_id):
        self._existing_id = existing_id

    def get_id_if_exists(self, _path):
        return self._existing_id


class _Pipeline:
    def __init__(self, *, existing_names=(), fail=False):
        self._existing_names = set(existing_names)
        self._fail = fail
        self.stream_calls = []

    def route(self, path):
        existing_id = f"existing:{path.name}" if path.name in self._existing_names else None
        return _Route(existing_id)

    def stream(self, files, *, reindex):
        self.stream_calls.append((list(files), reindex))
        if self._fail:
            raise RuntimeError("pipeline exploded")
        for path in files:
            yield SimpleNamespace(
                channel="index",
                content={"status": "success", "file_name": Path(path).name},
            )
        yield SimpleNamespace(channel="debug", text="indexed")
        return ([f"source:{Path(path).name}" for path in files], [], [])


class _Index:
    id = 7

    def __init__(self, pipeline, config=None):
        self.pipeline = pipeline
        self.config = dict(config or {})
        self.settings_seen = []

    def get_indexing_pipeline(self, settings, user_id):
        self.settings_seen.append((dict(settings), user_id))
        return self.pipeline


def _indexing_service(tmp_path, index, notices):
    return FileIndexingService(
        index=index,
        supported_file_types=[".txt"],
        zip_input_dir=tmp_path / "zip",
        engine=object(),
        demo_mode=False,
        notify=lambda level, message: notices.append((level, message)),
    )


def test_indexing_service_preserves_stream_payload_and_return_ids(tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("report", encoding="utf-8")
    notices = []
    pipeline = _Pipeline()
    service = _indexing_service(tmp_path, _Index(pipeline), notices)

    updates, returned = _drain(
        service.index(
            [str(source)],
            "",
            reindex=True,
            settings={"reader": "default"},
            user_id="user-1",
        )
    )

    assert updates == [
        ("✅ | report.txt", ""),
        ("✅ | report.txt", "indexed"),
    ]
    assert returned == ["source:report.txt"]
    assert notices == [
        ("info", "Start indexing 1 files..."),
        ("info", "Successfully index 1 files"),
    ]
    assert pipeline.stream_calls == [([str(source)], True)]


def test_indexing_service_logs_actionable_pipeline_failure(tmp_path, caplog):
    source = tmp_path / "report.txt"
    source.write_text("report", encoding="utf-8")
    service = _indexing_service(tmp_path, _Index(_Pipeline(fail=True)), [])

    with caplog.at_level("ERROR"):
        updates, returned = _drain(
            service.index(
                [str(source)],
                "",
                reindex=False,
                settings={},
                user_id="user-1",
            )
        )

    assert updates == [("", "Error: pipeline exploded")]
    assert returned is None
    assert "index_id=7" in caplog.text
    assert "user_id=user-1" in caplog.text
    assert "stage=stream" in caplog.text


def test_default_loader_indexing_preserves_existing_ids_and_setting_overrides(
    tmp_path,
):
    existing = tmp_path / "existing.txt"
    new = tmp_path / "new.txt"
    existing.write_text("old", encoding="utf-8")
    new.write_text("new", encoding="utf-8")
    pipeline = _Pipeline(existing_names={existing.name})
    index = _Index(pipeline)
    service = _indexing_service(tmp_path, index, [])
    original_settings = {"unchanged": True}

    returned = service.index_files_with_default_loaders(
        [str(existing), str(new)],
        reindex=False,
        settings=original_settings,
        user_id="user-1",
    )

    assert returned == ["existing:existing.txt", "source:new.txt"]
    assert original_settings == {"unchanged": True}
    assert any(
        settings["index.options.7.reader_mode"] == "default"
        and settings["index.options.7.quick_index_mode"] is True
        for settings, _user_id in index.settings_seen
    )


def _group_index(group_model):
    return SimpleNamespace(
        config={"private": True},
        _resources={"FileGroup": group_model},
    )


@pytest.fixture
def group_database():
    base = declarative_base()

    class FileGroup(base):
        __tablename__ = "test_file_group"
        id = Column(String, primary_key=True)
        name = Column(String)
        user = Column(String)
        data = Column(MutableDict.as_mutable(JSON), default={"files": []})
        date_created = Column(DateTime, default=datetime.now)

    db_engine = create_engine("sqlite://")
    base.metadata.create_all(db_engine)
    return FileGroup, db_engine


def test_group_service_preserves_rows_selection_update_and_delete(group_database):
    group_model, db_engine = group_database
    service = FileGroupService(index=_group_index(group_model), engine=db_engine)

    group_id = service.save_group(
        None,
        "Research",
        ["file-1", "file-2"],
        "user-1",
    )
    rows, frame = service.list_groups(
        "user-1",
        [
            {"id": "file-1", "name": "Alpha.pdf"},
            {"id": "file-2", "name": "Beta.pdf"},
        ],
    )

    assert rows[0]["id"] == group_id
    assert rows[0]["files"] == ["file-1", "file-2"]
    assert frame.iloc[0]["files"] == "[2 items] 'Alpha.pdf', 'Beta.pdf'"
    assert service.selected_file_ids(group_id) == ['["file-1", "file-2"]']

    assert service.save_group(group_id, "Renamed", ["file-2"], "user-1") == (
        group_id
    )
    updated_rows, _frame = service.list_groups(
        "user-1", [{"id": "file-2", "name": "Beta.pdf"}]
    )
    assert updated_rows[0]["name"] == "Renamed"
    assert updated_rows[0]["files"] == ["file-2"]

    assert service.delete_group(group_id) == "Renamed"
    empty_rows, empty_frame = service.list_groups("user-1", [])
    assert empty_rows == []
    assert empty_frame.iloc[0].to_dict() == {
        "id": "-",
        "name": "-",
        "files": "-",
        "date_created": "-",
    }


def test_group_service_rejects_duplicate_names(group_database):
    group_model, db_engine = group_database
    service = FileGroupService(index=_group_index(group_model), engine=db_engine)
    service.save_group(None, "Research", [], "user-1")

    with pytest.raises(GroupServiceError, match="already exists"):
        service.save_group(None, "Research", [], "user-1")


def test_group_service_keeps_private_user_scope(group_database):
    group_model, db_engine = group_database
    service = FileGroupService(index=_group_index(group_model), engine=db_engine)
    service.save_group(None, "Alice", [], "alice")
    service.save_group(None, "Bob", [], "bob")

    rows, _frame = service.list_groups("alice", [])

    assert [row["name"] for row in rows] == ["Alice"]
