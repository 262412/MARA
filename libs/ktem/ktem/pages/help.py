from importlib.metadata import version
from pathlib import Path
import re

import gradio as gr
import requests
from decouple import config
from theflow.settings import settings

from ktem.utils.render import BASE_PATH

KH_DEMO_MODE = getattr(settings, "KH_DEMO_MODE", False)
HF_SPACE_URL = config("HF_SPACE_URL", default="")
LOCAL_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^]]*)]\(([^)\s]+)\)")


def _rewrite_local_image_links(markdown: str, doc_dir: str | Path) -> str:
    doc_dir = Path(doc_dir)

    def replace(match: re.Match[str]) -> str:
        alt_text, image_link = match.groups()
        if image_link.startswith(("http://", "https://", "data:", "#", "/file=")):
            return match.group(0)

        image_path = Path(image_link)
        if not image_path.is_absolute():
            image_path = doc_dir / image_path
        image_path = image_path.resolve()
        if not image_path.exists():
            return match.group(0)

        return f"![{alt_text}]({BASE_PATH}/file={image_path.as_posix()})"

    return LOCAL_MARKDOWN_IMAGE_RE.sub(replace, markdown)


def get_remote_doc(url: str) -> str:
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.text
    except Exception as e:
        print(f"Failed to fetch document from {url}: {e}")
        return ""


def download_changelogs(release_url: str) -> str:
    try:
        res = requests.get(release_url).json()
        changelogs = res.get("body", "")

        return changelogs
    except Exception as e:
        print(f"Failed to fetch changelogs from {release_url}: {e}")
        return ""


class HelpPage:
    def __init__(
        self,
        app,
        doc_dir: str = settings.KH_DOC_DIR,
        remote_content_url: str = "https://raw.githubusercontent.com/Cinnamon/kotaemon",
        app_version: str | None = settings.KH_APP_VERSION,
        changelogs_cache_dir: str
        | Path = (Path(settings.KH_APP_DATA_DIR) / "changelogs"),
    ):
        self._app = app
        self.doc_dir = Path(doc_dir)
        self.remote_content_url = remote_content_url
        self.app_version = app_version
        self.changelogs_cache_dir = Path(changelogs_cache_dir)

        self.changelogs_cache_dir.mkdir(parents=True, exist_ok=True)

        about_md = self._load_doc_markdown("about.md")
        if about_md:
            with gr.Accordion("About"):
                if self.app_version:
                    about_md = f"Version: {self.app_version}\n\n{about_md}"
                gr.Markdown(about_md)

        if KH_DEMO_MODE:
            with gr.Accordion("Create Your Own Space"):
                gr.Markdown(
                    "This is a demo with limited functionality. "
                    "Use **Create space** button to install MARA "
                    "in your own space with all features "
                    "(including upload and manage your private "
                    "documents securely)."
                )
                gr.Button(
                    value="Create Your Own Space",
                    link=HF_SPACE_URL,
                    variant="primary",
                    size="lg",
                )

        user_guide_md = self._load_doc_markdown("usage.md")
        if user_guide_md:
            with gr.Accordion("User Guide", open=not KH_DEMO_MODE):
                gr.Markdown(user_guide_md)

        if self.app_version:
            # try retrieve from cache
            changelogs = ""

            if (self.changelogs_cache_dir / f"{version}.md").exists():
                with open(self.changelogs_cache_dir / f"{version}.md", "r") as fi:
                    changelogs = fi.read()
            else:
                release_url_base = (
                    "https://api.github.com/repos/Cinnamon/kotaemon/releases"
                )
                changelogs = download_changelogs(
                    release_url=f"{release_url_base}/tags/v{self.app_version}"
                )

                # cache the changelogs
                if not self.changelogs_cache_dir.exists():
                    self.changelogs_cache_dir.mkdir(parents=True, exist_ok=True)
                with open(
                    self.changelogs_cache_dir / f"{self.app_version}.md", "w"
                ) as fi:
                    fi.write(changelogs)

            if changelogs:
                with gr.Accordion(f"Changelogs (v{self.app_version})"):
                    gr.Markdown(changelogs)

    def _load_doc_markdown(self, filename: str) -> str:
        doc_path = self.doc_dir / filename
        if doc_path.exists():
            markdown = doc_path.read_text(encoding="utf-8")
            return _rewrite_local_image_links(markdown, self.doc_dir)

        return get_remote_doc(
            f"{self.remote_content_url}/v{self.app_version}/docs/{filename}"
        )
