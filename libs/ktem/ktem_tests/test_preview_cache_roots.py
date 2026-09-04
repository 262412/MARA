def test_office_cache_root_expands_user_and_becomes_absolute(monkeypatch, tmp_path):
    from ktem.preview.office import OfficeConversionService

    home = tmp_path / "home"
    working = tmp_path / "working"
    home.mkdir()
    working.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(working)

    service = OfficeConversionService("~/cache/../office-cache")

    assert service.cache_dir == home / "office-cache"
    assert service.cache_dir.is_absolute()
