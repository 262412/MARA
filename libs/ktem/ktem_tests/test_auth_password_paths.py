from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SECURITY_PASSWORD_FILES = [
    REPO_ROOT / "libs/ktem/ktem/pages/login.py",
    REPO_ROOT / "libs/ktem/ktem/pages/resources/user.py",
    REPO_ROOT / "libs/ktem/ktem/pages/settings.py",
    REPO_ROOT / "libs/ktem/ktem/docqa/runtime.py",
]


@pytest.mark.parametrize("source_path", SECURITY_PASSWORD_FILES)
def test_security_password_paths_do_not_hash_with_sha256(source_path):
    source = source_path.read_text(encoding="utf-8")

    assert "hashlib.sha256" not in source


def test_ktem_declares_bcrypt_as_a_direct_runtime_dependency():
    pyproject = (REPO_ROOT / "libs/ktem/pyproject.toml").read_text(encoding="utf-8")

    assert '"bcrypt' in pyproject
