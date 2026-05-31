from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ktem"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_copy_uses_mara_branding():
    about = _read(PACKAGE_ROOT / "assets" / "md" / "about.md")
    changelogs = _read(PACKAGE_ROOT / "assets" / "md" / "changelogs.md")
    chat_panel = _read(PACKAGE_ROOT / "pages" / "chat" / "chat_panel.py")

    assert "# About MARA" in about
    assert "MARA is a branded fork" in about
    assert "Slides Demo" not in chat_panel
    assert "show MARA and upstream project information" in changelogs
