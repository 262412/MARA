from ktem.runtime_bootstrap import get_runtime_paths


def test_desktop_runtime_paths_stay_inside_the_desktop_data_root(
    monkeypatch,
    tmp_path,
):
    desktop_root = tmp_path / "MARA"
    monkeypatch.setenv("MARA_DESKTOP_DATA_DIR", str(desktop_root))

    paths = get_runtime_paths()

    assert paths.config_dir == (desktop_root / "state" / "config").resolve()
    assert paths.data_dir == (desktop_root / "state" / "runtime").resolve()
    assert paths.cache_dir == (desktop_root / "cache").resolve()
    assert paths.flowsettings_path == paths.config_dir / "flowsettings.py"
    assert paths.env_path == paths.config_dir / ".env"
