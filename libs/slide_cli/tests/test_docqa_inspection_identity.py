"""Real CLI and Sidecar collectors must keep owner/public SQL filtering."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pytest_runtime_isolation import activate_test_runtime

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def managed_environment(tmp_path):
    env = os.environ.copy()
    _, paths = activate_test_runtime(env, tmp_path / "owned")
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO / "apps/desktop"),
            str(REPO / "libs/slide_cli"),
            str(REPO / "libs/ktem"),
            str(REPO / "libs/kotaemon"),
        ]
    )
    (paths.root / "config/flowsettings.py").write_text(
        "KH_FEATURE_USER_MANAGEMENT = True\n"
        "KH_FEATURE_USER_MANAGEMENT_ADMIN = ''\n"
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD = ''\n",
        encoding="utf-8",
    )
    seed = """
from ktem.db.models import Conversation, User
from ktem.db.engine import engine
from sqlmodel import Session
with Session(engine) as session:
    session.add(User(id='other-owner', username='Other', username_lower='other',
                     password='task-owned-placeholder', admin=False))
    session.add(Conversation(id='private-other', user='other-owner', name='PRIVATE SENTINEL'))
    session.add(Conversation(id='public-other', user='other-owner', name='Public', is_public=True))
    session.commit()
engine.dispose()
"""
    result = subprocess.run(
        [sys.executable, "-c", seed],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return env, tmp_path


@pytest.mark.parametrize("entry", ["cli", "sidecar", "doctor"])
def test_missing_managed_identity_never_lists_other_owner_private_sessions(
    managed_environment, entry
):
    env, cwd = managed_environment
    if entry in {"cli", "doctor"}:
        command = [
            sys.executable,
            "-m",
            "slide_cli.cli",
            "docqa",
            "doctor" if entry == "doctor" else "sessions",
            "--json",
        ]
    else:
        command = [
            sys.executable,
            "-c",
            "import json; from sidecar.application import DesktopApplicationService; "
            "print(json.dumps(DesktopApplicationService().list_sessions()))",
        ]
    result = subprocess.run(
        command,
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == (1 if entry == "doctor" else 0), result.stderr
    payload = json.loads(result.stdout)
    if entry == "doctor":
        assert payload["ok"] is False
        assert payload["default_user_id"] == ""
        assert any("No managed default user" in issue for issue in payload["issues"])
        assert payload["session_count"] == 1
    else:
        assert [row["conversation_id"] for row in payload] == ["public-other"]
        assert "PRIVATE SENTINEL" not in result.stdout
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from ktem.db.engine import engine; "
            "from ktem.db.models import User; from sqlmodel import Session,select; "
            "s=Session(engine); print(json.dumps([(u.id,u.admin) for u in s.exec(select(User)).all()])); s.close()",
        ],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert check.returncode == 0, check.stderr
    assert json.loads(check.stdout) == [["other-owner", False]]
