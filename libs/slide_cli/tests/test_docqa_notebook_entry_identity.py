"""Exercise real Notebook services through the CLI, including public non-owners."""

import json
import os
import subprocess
import sys
from pathlib import Path

from pytest_runtime_isolation import activate_test_runtime

ENTRY_SCRIPT = """
import json
from click.testing import CliRunner
from ktem.db.engine import engine
from ktem.db.models import Conversation, User
from ktem.docqa import _runtime_notebook as notebook
from slide_cli.cli import main
from sqlmodel import Session
with Session(engine) as session:
    session.add(User(id='owner', username='Operator', username_lower='operator', password='test-only', admin=False))
    for identifier, owner, public in [('owned', 'owner', False), ('private', 'other', False), ('public', 'other', True)]:
        session.add(Conversation(id=identifier, user=owner, name=identifier, is_public=public,
                                 data_source={'messages': [['question', 'saved answer']]}))
    session.commit()
for identifier, owner in [('owned', 'owner'), ('private', 'other'), ('public', 'other')]:
    notebook.add_note_to_conversation(identifier, user_id=owner, title='Original', text='private notebook sentinel')
    notebook.save_artifact_to_conversation(identifier, user_id=owner, artifact_id='artifact-one',
        artifact_type='study_guide', payload={'content': 'Task-owned study guide'}, title='Guide')
runner = CliRunner()
commands = [
    ['notes', 'list', 'owned', '--json'],
    ['notes', 'add', 'owned', '--text', 'Added through CLI', '--json'],
    ['notes', 'save-answer', 'owned', '--json'],
    ['sources', 'list', 'owned', '--json'],
    ['artifacts', 'list', 'owned', '--json'],
    ['artifacts', 'show', 'owned', '--artifact', 'artifact-one', '--json'],
    ['artifacts', 'export', 'owned', '--artifact', 'artifact-one', '--format', 'json', '--output', 'owned-export.json', '--json'],
    ['artifacts', 'evaluate', 'owned', '--artifact', 'artifact-one', '--json'],
    ['artifacts', 'save-note', 'owned', '--artifact', 'artifact-one', '--json'],
    ['artifacts', 'delete', 'owned', '--artifact', 'artifact-one', '--json'],
    ['notes', 'list', 'private', '--json'],
    ['notes', 'list', 'public', '--json'],
    ['notes', 'add', 'public', '--text', 'forbidden', '--json'],
    ['artifacts', 'delete', 'public', '--artifact', 'artifact-one', '--json'],
]
results = []
for arguments in commands:
    result = runner.invoke(main, ['docqa', *arguments])
    results.append({'args': arguments, 'exit': result.exit_code, 'output': result.output,
                    'error_type': type(result.exception).__name__ if result.exception else None,
                    'error': str(result.exception) if result.exception else ''})
unchanged = notebook.get_notebook('public', user_id='other')
print(json.dumps({'results': results, 'public_notes': len(unchanged['notes']),
                  'public_artifacts': len(unchanged['artifacts'])}))
engine.dispose()
"""


def test_real_notebook_cli_uses_runtime_identity_and_keeps_public_writes_forbidden(
    tmp_path,
):
    env = os.environ.copy()
    _, paths = activate_test_runtime(env, tmp_path / "owned-runtime")
    repo = Path(__file__).resolve().parents[3]
    env["PYTHONPATH"] = os.pathsep.join(
        str(repo / "libs" / package) for package in ("slide_cli", "ktem", "kotaemon")
    )
    (paths.root / "config/flowsettings.py").write_text(
        "KH_FEATURE_USER_MANAGEMENT = True\n"
        "KH_FEATURE_USER_MANAGEMENT_ADMIN = 'Operator'\n"
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD = ''\n"
        "KH_LLMS = {}\nKH_EMBEDDINGS = {}\nKH_RERANKINGS = {}\n"
        "KH_REASONINGS = []\nKH_WEB_SEARCH_BACKEND = None\n"
        "KH_ENABLE_FILE_ARTIFACTS = False\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", ENTRY_SCRIPT],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    owned = payload["results"][:10]
    assert all(item["exit"] == 0 for item in owned), owned
    for item in owned:
        json.loads(item["output"])
    denied = payload["results"][10:]
    assert all(item["exit"] == 1 for item in denied), denied
    assert denied[0]["error_type"] == "SystemExit"
    assert all(item["error_type"] == "NotebookAccessError" for item in denied[1:])
    assert all("private notebook sentinel" not in item["output"] for item in denied)
    assert (payload["public_notes"], payload["public_artifacts"]) == (1, 1)
