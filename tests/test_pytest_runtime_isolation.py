from __future__ import annotations

import hashlib
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _fingerprint(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_environment_overrides_real_candidate_and_restores_it(tmp_path):
    from pytest_runtime_isolation import (
        ISOLATED_RUNTIME_ENV_KEYS,
        activate_test_runtime,
        restore_environment,
    )

    real_candidate = tmp_path / "real-runtime-candidate"
    real_database = real_candidate / "user_data" / "sql.db"
    real_file = real_candidate / "user_data" / "files" / "sentinel.pdf"
    real_database.parent.mkdir(parents=True)
    real_file.parent.mkdir(parents=True)
    real_database.write_bytes(b"do not mutate this database")
    real_file.write_bytes(b"do not mutate this stored file")
    before = {
        real_database: _fingerprint(real_database),
        real_file: _fingerprint(real_file),
    }

    environment = {
        key: str(real_candidate / key.lower()) for key in ISOLATED_RUNTIME_ENV_KEYS
    }
    environment["KH_APP_DATA_DIR"] = str(real_candidate)
    environment["KH_DATABASE"] = f"sqlite:///{real_database}"
    environment["KH_FILESTORAGE_PATH"] = str(real_file.parent)
    original_environment = dict(environment)

    session_root = tmp_path / "session-owned-runtime"
    snapshot, paths = activate_test_runtime(environment, session_root)

    assert Path(environment["KH_APP_DATA_DIR"]) == paths.app_data_dir
    assert environment["KH_DATABASE"] == f"sqlite:///{paths.database_path}"
    assert Path(environment["KH_FILESTORAGE_PATH"]) == paths.file_storage_path
    for key in ISOLATED_RUNTIME_ENV_KEYS:
        assert str(real_candidate) not in environment[key]
        assert Path(environment[key].removeprefix("sqlite:///")).is_relative_to(
            session_root
        )

    paths.database_path.parent.mkdir(parents=True, exist_ok=True)
    paths.file_storage_path.mkdir(parents=True, exist_ok=True)
    paths.database_path.write_bytes(b"isolated test database")
    (paths.file_storage_path / "isolated.pdf").write_bytes(b"isolated file")

    restore_environment(environment, snapshot)

    assert environment == original_environment
    assert {
        real_database: _fingerprint(real_database),
        real_file: _fingerprint(real_file),
    } == before


def test_pytest_session_activates_isolation_before_ktem_runtime_import(
    mara_test_runtime_paths,
):
    from theflow.settings import settings as flowsettings

    assert Path(os.environ["KH_APP_DATA_DIR"]) == mara_test_runtime_paths.app_data_dir
    assert Path(flowsettings.KH_APP_DATA_DIR) == mara_test_runtime_paths.app_data_dir
    assert flowsettings.KH_DATABASE == (
        f"sqlite:///{mara_test_runtime_paths.database_path}"
    )
    assert Path(flowsettings.KH_FILESTORAGE_PATH) == (
        mara_test_runtime_paths.file_storage_path
    )


def test_root_pytest_configuration_uses_importlib_collection_mode():
    source = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "[tool.pytest.ini_options]" in source
    assert 'addopts = "--import-mode=importlib"' in source
