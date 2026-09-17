"""Keep the full-App response observer's lifecycle boundary in the root suite."""

import subprocess
from pathlib import Path


def test_queue_response_observer_contracts():
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "--test", "tests/browser/queue_response_observer.test.cjs"],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
