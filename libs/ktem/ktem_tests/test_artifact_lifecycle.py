from types import SimpleNamespace


def test_file_artifacts_default_off_on_non_posix(monkeypatch):
    from ktem.index.file import artifact_lifecycle as module

    monkeypatch.setattr(module.os, "name", "nt")

    assert module._enabled(SimpleNamespace()) is False
