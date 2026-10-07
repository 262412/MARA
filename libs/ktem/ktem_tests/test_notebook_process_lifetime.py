"""Same-host processes coordinate a row; unrelated conversations can progress."""

import os
import subprocess
import sys

import pytest
from filelock import Timeout
from ktem.db.models import Conversation
from ktem.docqa import _runtime_notebook as notebook
from ktem.docqa.conversation_lifetime import conversation_write
from sqlmodel import Session

from . import test_notebook_commit_interleavings as notebook_fixtures
from .test_storage_lifetime_processes import wait_marker

store = notebook_fixtures.store
_add = notebook_fixtures._add


def test_independent_processes_preserve_notes_and_release_row_leases(store, tmp_path):
    engine, cid, _sessions, _mutations = store
    barrier = tmp_path / "process-barrier"
    barrier.mkdir()
    with Session(engine) as session:
        session.add(Conversation(id="independent", user="owner"))
        session.commit()
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-m",
            "ktem_tests.notebook_process_probe",
            str(engine.url),
            cid,
            str(barrier),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    try:
        wait_marker(barrier / "blocked", process)
        with pytest.raises(Timeout):
            conversation_write(engine, cid).acquire(timeout=0)
        _add("independent", "other-row")
    finally:
        (barrier / "release").write_text("release owned producer")
        try:
            output = process.communicate(timeout=35)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
            raise
        assert process.returncode == 0, output
    _add(cid, "parent")
    notes = notebook.get_notebook(cid, user_id="owner")["notes"]
    assert {note["note_id"] for note in notes} == {"process", "parent"}
    assert (
        notebook.get_notebook("independent", user_id="owner")["notes"][0]["note_id"]
        == "other-row"
    )
    with conversation_write(engine, cid).acquire(timeout=0):
        pass
