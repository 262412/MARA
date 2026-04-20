from types import SimpleNamespace

from ktem.utils.dependencies import DependencyChecker, find_soffice_binary


def test_find_soffice_binary_prefers_env_path(monkeypatch, tmp_path):
    soffice_path = tmp_path / "soffice"
    soffice_path.write_text("", encoding="utf-8")

    monkeypatch.setenv("SOFFICE_PATH", str(soffice_path))
    monkeypatch.setattr("ktem.utils.dependencies.shutil.which", lambda _command: None)

    assert find_soffice_binary() == str(soffice_path)


def test_check_libreoffice_uses_shared_locator(monkeypatch):
    monkeypatch.setattr(
        "ktem.utils.dependencies.find_soffice_binary",
        lambda: "/opt/libreoffice/program/soffice",
    )
    monkeypatch.setattr(
        "ktem.utils.dependencies.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="LibreOffice 24.2", stderr=""
        ),
    )

    ok, info = DependencyChecker.check_libreoffice()

    assert ok is True
    assert info == "LibreOffice 24.2"
