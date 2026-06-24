from pathlib import Path
import re

from ktem.pages.help import _rewrite_local_image_links

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


def test_help_markdown_rewrites_local_images_to_gradio_file_routes(tmp_path):
    doc_dir = tmp_path / "docs"
    image_dir = doc_dir / "images"
    image_dir.mkdir(parents=True)
    local_image = image_dir / "resources-tab.png"
    local_image.write_bytes(b"png")

    markdown = "\n".join(
        [
            "![MARA resources tab](images/resources-tab.png)",
            "![Remote image](https://example.com/remote.png)",
            "![Missing image](images/missing.png)",
        ]
    )

    rewritten = _rewrite_local_image_links(markdown, doc_dir)

    assert (
        f"![MARA resources tab](/file={local_image.resolve().as_posix()})"
        in rewritten
    )
    assert "![Remote image](https://example.com/remote.png)" in rewritten
    assert "![Missing image](images/missing.png)" in rewritten


def test_packaged_help_image_links_have_assets():
    usage = _read(PACKAGE_ROOT / "assets" / "md" / "usage.md")
    image_links = re.findall(r"!\[[^]]*]\(([^)]+)\)", usage)

    assert image_links
    for image_link in image_links:
        assert (PACKAGE_ROOT / "assets" / "md" / image_link).resolve().exists()
