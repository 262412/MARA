"""The Gradio prediction and HTTP file routes must share the current owner scope."""

import os
from types import SimpleNamespace

import gradio as gr
import pytest
from fastapi.testclient import TestClient
from gradio.routes import App
from ktem.auth import service as auth
from ktem.db.models import User
from ktem.index.file import _scoped_page as page_module
from ktem.index.file._selection_service import FileSelectionService
from sqlalchemy import Column, String
from sqlalchemy.orm import declarative_base
from sqlmodel import Session, create_engine
from theflow.settings import settings

from .download_http_test_support import NativeProducer


@pytest.fixture
def download_app(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'http.db'}")
    base = declarative_base()

    class Source(base):  # type: ignore[valid-type,misc]
        __tablename__ = "http_owned_source"
        id = Column(String, primary_key=True)
        user = Column(String)
        name = Column(String)

    base.metadata.create_all(engine)
    User.__table__.create(engine)
    with Session(engine) as session:
        for user in ("owner", "other"):
            session.add(
                User(id=user, username=user, username_lower=user, password="test")
            )
        session.add(Source(id="file", user="owner", name="owned.txt"))
        session.commit()
    monkeypatch.setattr(auth, "engine", engine)
    monkeypatch.setattr(settings, "MARA_AUTH_MODE", "password", raising=False)
    monkeypatch.setattr(
        settings, "KH_ZIP_OUTPUT_DIR", str(tmp_path / "zip"), raising=False
    )
    index = SimpleNamespace(
        id=1, config={"private": True}, _resources={"Source": Source}
    )
    selection = FileSelectionService(index=index, engine=engine, sort_key=lambda doc: 0)

    class Page(page_module.ScopedFileIndexPageMixin):
        _index = index

        def _get_file_selection_service(self):
            return selection

    # Native Windows cannot allocate secure dir_fds. Only the generation fixture
    # is substituted here; the HTTP consumer must still enforce its capability.
    if os.name != "posix":
        monkeypatch.setattr(page_module.DownloadWorkspace, "create", NativeProducer)

    app, blocks = _http_app(Page(), index, engine)
    with TestClient(app) as owner, TestClient(app) as other:
        assert (
            owner.post(
                "/login", data={"username": "owner", "password": "fixture"}
            ).status_code
            == 200
        )
        assert (
            other.post(
                "/login", data={"username": "other", "password": "fixture"}
            ).status_code
            == 200
        )
        response = owner.post(
            "/run/owned_download",
            json={
                "data": [False, "OWNER-BYTES", "file", "spoof"],
                "session_hash": "owner",
            },
        )
        assert response.status_code == 200, response.text
        url = response.json()["data"][1]["value"]["url"]
        yield SimpleNamespace(
            owner=owner,
            other=other,
            url=url,
            engine=engine,
            Source=Source,
            blocks=blocks,
        )
    engine.dispose()


def _http_app(page, index, engine):
    from ktem.index.file.download_http import DownloadButton, download_app_kwargs

    kwargs = download_app_kwargs(
        SimpleNamespace(index_manager=SimpleNamespace(indices=[index])), engine=engine
    )
    with gr.Blocks(analytics_enabled=False) as blocks:
        state, html, file_id, user_id = (
            gr.Checkbox(),
            gr.Textbox(),
            gr.Textbox(),
            gr.Textbox(),
        )
        button = DownloadButton()
        button.click(
            page.download_single_file_simple,
            [state, html, file_id, user_id],
            [state, button],
            api_name="owned_download",
            queue=False,
        )
    blocks.auth = (
        lambda user, password: user in {"owner", "other"} and password == "fixture"
    )
    app = App.create_app(blocks, app_kwargs=kwargs)
    return app, blocks


def test_generated_download_does_not_become_a_shared_gradio_cache_file(download_app):
    fixture = download_app
    response = fixture.other.get(fixture.url)
    assert response.status_code in {403, 404}
    assert b"OWNER-BYTES" not in response.content
    assert "/mara-download/" in fixture.url
    assert not any(
        "download-" in str(path)
        for files in fixture.blocks.temp_file_sets
        for path in files
    )


@pytest.mark.parametrize("change", ["delete", "revoke"])
def test_http_get_revalidates_source_after_generation(download_app, change):
    fixture = download_app
    with Session(fixture.engine) as session:
        source = session.get(fixture.Source, "file")
        assert source is not None
        if change == "delete":
            session.delete(source)
        else:
            source.user = "other"
            session.add(source)
        session.commit()
    assert fixture.owner.get(fixture.url).status_code in {403, 404}


def test_http_bytes_head_range_and_native_capability(download_app):
    fixture = download_app
    response = fixture.owner.get(fixture.url)
    if os.name != "posix":
        assert response.status_code == 503
        assert b"OWNER-BYTES" not in response.content
        return
    assert response.status_code == 200
    assert response.content == b"OWNER-BYTES"
    assert response.headers["cache-control"] == "private, no-store"
    head = fixture.owner.head(fixture.url)
    assert head.status_code == 200 and head.content == b""
    assert head.headers["content-length"] == str(len(b"OWNER-BYTES"))
    partial = fixture.owner.get(fixture.url, headers={"Range": "bytes=2-5"})
    assert partial.status_code == 206 and partial.content == b"NER-"
    assert partial.headers["content-range"] == "bytes 2-5/11"
    assert (
        fixture.owner.get(fixture.url, headers={"Range": "bytes=80-90"}).status_code
        == 416
    )
