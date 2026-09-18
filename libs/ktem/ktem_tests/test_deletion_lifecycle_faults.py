"""Baseline resource states, including irreversible external partial progress."""

import pytest
from ktem.index.file.deletion import DeletionError

from . import test_deletion_coordinator as fixtures
from .deletion_fault_test_support import FaultProbe
from .test_deletion_coordinator import _coordinator, _row_counts, _seed_file

deletion_db = fixtures.deletion_db

SUCCESS_TRACE = [
    "vector",
    "docstore",
    "fts",
    "artifacts",
    "lease",
    "sql-index",
    "flush",
    "sql-source",
    "flush",
    "flush",
    "references",
    "flush",
    "quarantine",
    "commit",
    "purge",
]


def failure_trace(failure):
    if failure == "restore":
        return SUCCESS_TRACE[:-1] + ["rollback", "restore"]
    if failure == "sync":
        return SUCCESS_TRACE[:-2] + ["sync", "restore", "rollback"]
    trace = SUCCESS_TRACE[: SUCCESS_TRACE.index(failure) + 1]
    if failure == "quarantine":
        trace += ["rollback"]
    if failure == "commit":
        trace += ["rollback", "restore"]
    return trace


@pytest.mark.parametrize(
    "failure,stage,documents,artifacts,original,orphan",
    [
        ("vector", "vector", {"document-1", "element-1", "graph-1"}, 4, True, False),
        ("docstore", "docstore", {"element-1", "graph-1"}, 4, True, False),
        ("fts", "docstore", set(), 4, True, False),
        ("artifacts", "artifacts", set(), 3, True, False),
        ("lease", "disk", set(), 0, True, False),
        ("sql-index", "sql", set(), 0, True, False),
        ("sql-source", "sql", set(), 0, True, False),
        ("flush", "sql", set(), 0, True, False),
        ("references", "sql", set(), 0, True, False),
        ("quarantine", "disk", set(), 0, True, False),
        ("sync", "disk", set(), 0, True, False),
        ("commit", "sql", set(), 0, True, False),
        ("restore", "sql", set(), 0, False, True),
    ],
)
def test_failure_keeps_sql_but_not_external_progress(
    deletion_db,
    tmp_path,
    caplog,
    failure,
    stage,
    documents,
    artifacts,
    original,
    orphan,
):
    _seed_file(deletion_db)
    probe = FaultProbe(deletion_db, tmp_path, failure)
    with pytest.raises(DeletionError) as raised:
        probe.coordinator().delete("file-1", user_id="user-1")
    assert raised.value.stage == stage and raised.value.file_id == "file-1"
    assert probe.trace == failure_trace(failure)
    assert _row_counts(deletion_db) == (1, 4)
    assert probe.vector.values == set()
    assert probe.docstore.values == documents
    assert sum(path.exists() for path in probe.artifacts) == artifacts
    assert (deletion_db[3] / "stored.bin").exists() is original
    quarantines = list(deletion_db[3].glob(".stored.bin.quarantine-*"))
    assert bool(quarantines) is orphan
    if orphan:
        assert quarantines[0].read_bytes() == b"document"
        assert "restore failed: OSError: injected restore" in raised.value.reason
        assert "Failed to restore quarantined source" in caplog.text
    else:
        assert (deletion_db[3] / "stored.bin").read_bytes() == b"document"
        assert not caplog.records

    # A retry tolerates missing external IDs; it does not recover a prior orphan.
    probe.failure = None
    assert probe.coordinator().delete("file-1", user_id="user-1").file_id == "file-1"
    assert _row_counts(deletion_db) == (0, 0)
    assert probe.vector.values == probe.docstore.values == set()
    assert not any(path.exists() for path in probe.artifacts)
    assert not (deletion_db[3] / "stored.bin").exists()
    assert list(deletion_db[3].glob(".stored.bin.quarantine-*")) == quarantines


def test_postcommit_purge_failure_returns_success_and_retry_cannot_clean_orphan(
    deletion_db, tmp_path, caplog
):
    _seed_file(deletion_db)
    probe = FaultProbe(deletion_db, tmp_path, "purge")
    assert probe.coordinator().delete("file-1", user_id="user-1").name == "report.pdf"
    assert _row_counts(deletion_db) == (0, 0)
    assert probe.vector.values == probe.docstore.values == set()
    assert not any(path.exists() for path in probe.artifacts)
    assert not (deletion_db[3] / "stored.bin").exists()
    [orphan] = list(deletion_db[3].glob(".stored.bin.quarantine-*"))
    assert orphan.read_bytes() == b"document"
    assert (
        "Committed deletion left auditable storage orphan file_id=file-1" in caplog.text
    )
    before = probe.trace.copy()
    with pytest.raises(DeletionError) as raised:
        probe.coordinator().delete("file-1", user_id="user-1")
    assert raised.value.stage == "validate"
    assert probe.trace == before and orphan.exists()


def test_successful_lifecycle_has_fixed_phase_order(deletion_db, tmp_path):
    _seed_file(deletion_db)
    probe = FaultProbe(deletion_db, tmp_path, None)
    probe.coordinator().delete("file-1", user_id="user-1")
    assert probe.trace == SUCCESS_TRACE


@pytest.mark.parametrize(
    "file_id,user_id",
    [("", "user-1"), ("file-1", None), ("missing", "user-1"), ("file-1", "other")],
)
def test_authority_failure_precedes_every_external_operation(
    deletion_db, tmp_path, file_id, user_id
):
    _seed_file(deletion_db)
    probe = FaultProbe(deletion_db, tmp_path, None)
    with pytest.raises(DeletionError) as raised:
        probe.coordinator().delete(file_id, user_id=user_id)
    assert raised.value.stage == "validate"
    assert probe.trace == [] and _row_counts(deletion_db) == (1, 4)


def test_changed_source_scope_rolls_back_relation_deletion(deletion_db, monkeypatch):
    from sqlalchemy.orm import Session

    _seed_file(deletion_db)
    subject = _coordinator(deletion_db)
    gather = subject._gather_plan

    def change_owner(*args):
        plan = gather(*args)
        with Session(deletion_db[0]) as session:
            source = session.get(deletion_db[1], "file-1")
            assert source is not None
            source.user = "new-owner"
            session.commit()
        return plan

    monkeypatch.setattr(subject, "_gather_plan", change_owner)
    with pytest.raises(DeletionError, match="source scope changed") as raised:
        subject.delete("file-1", user_id="user-1")
    assert raised.value.stage == "sql"
    assert _row_counts(deletion_db) == (1, 4)
    assert (deletion_db[3] / "stored.bin").read_bytes() == b"document"
