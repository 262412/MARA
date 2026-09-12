"""Own all resources while constructing the production App and message chain."""

from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast


@contextmanager
def submission_app(monkeypatch, root, *, demo_mode=False):
    from theflow.settings import settings

    from libs.kotaemon.tests.chroma_test_runtime import owned_chroma_stores

    docs = Path(settings.KH_DOC_DIR)
    assert docs.resolve().is_relative_to(root)
    docs.mkdir(parents=True, exist_ok=True)
    for name in ("about.md", "usage.md"):
        (docs / name).write_text("# Owned submission fixture", encoding="utf-8")
    monkeypatch.setattr(settings, "KH_APP_VERSION", "")
    monkeypatch.setattr(settings, "KH_DEMO_MODE", demo_mode)
    monkeypatch.setattr(settings, "MARA_AUTH_MODE", "password")
    monkeypatch.setattr(settings, "KH_FEATURE_USER_MANAGEMENT", True)
    monkeypatch.setattr(settings, "KH_ENABLE_FIRST_SETUP", False)
    from ktem.assets.pdfjs_assets import materialize_pdfjs

    materialize_pdfjs(app_data_dir=Path(settings.KH_APP_DATA_DIR))
    _configure_models(monkeypatch, settings)
    from ktem.auth.service import provision_password_admin
    from ktem.embeddings.manager import embedding_models_manager
    from ktem.index.file import index as index_module
    from ktem.llms.manager import llms
    from ktem.main import App
    from ktem.rerankings.manager import reranking_models_manager

    provision_password_admin(username="browser-owner", password="OwnedFixture7!")
    # Seed the owned provider tables before concurrent real app-load callbacks.
    llms.info()
    embedding_models_manager.info()
    reranking_models_manager.info()
    with owned_chroma_stores(root) as create_store:
        configuration = dict(settings.KH_VECTORSTORE)
        assert configuration.pop("__type__") == "kotaemon.storages.ChromaVectorStore"

        def vector_store(collection_name):
            return create_store(**configuration, collection_name=collection_name)

        monkeypatch.setattr(index_module, "get_vectorstore", vector_store)
        app = App()
        defaults = app.settings_state.value
        defaults["reasoning.use"] = "simple"
        for key in (
            "highlight_citation",
            "create_mindmap",
            "create_citation_viz",
            "verify_claims",
        ):
            defaults[f"reasoning.options.simple.{key}"] = (
                "off" if key == "highlight_citation" else False
            )
        for key in list(defaults):
            if key.endswith(".use_reranking"):
                defaults[key] = False
            if key.endswith(".retrieval_mode"):
                defaults[key] = "vector"
        for key, value in defaults.items():
            if key.startswith("index.options."):
                _, _, index_id, option = key.split(".", 3)
                group = cast(dict[Any, Any], app.default_settings.index.options)[
                    int(index_id)
                ]
                group.get_setting_item(option).value = value
            else:
                app.default_settings.get_setting_item(key).value = value
        blocks = app.make()
        try:
            yield app, blocks
        finally:
            blocks.close()


def _configure_models(monkeypatch, settings):
    module = "libs.ktem.ktem_tests.chat_submission_model_fixture"
    monkeypatch.setattr(
        settings,
        "KH_LLMS",
        {
            "owned": {
                "spec": {"__type__": f"{module}.SubmissionChatModel"},
                "default": True,
            }
        },
    )
    monkeypatch.setattr(
        settings,
        "KH_EMBEDDINGS",
        {
            "owned": {
                "spec": {"__type__": f"{module}.SubmissionEmbeddings"},
                "default": True,
            }
        },
    )
    monkeypatch.setattr(
        settings,
        "KH_RERANKINGS",
        {
            "owned": {
                "spec": {"__type__": "kotaemon.indices.rankings.LLMReranking"},
                "default": True,
            }
        },
    )


def seed_owned_document(app, root):
    import fitz
    from ktem.db.models import User, engine
    from sqlmodel import Session, select

    from kotaemon.base import DocumentWithEmbedding

    index = app.chat_page.file_index
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == "browser-owner")).one()
        user_id = user.id
    path = Path(index._resources["FileStoragePath"]) / "owned-observatory.pdf"
    assert path.resolve().is_relative_to(root)
    document = fitz.open()
    page = document.new_page()
    text = "The observatory has seven telescopes. This is an owned test document."
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    source_id, chunk_id = "owned-observatory", "owned-observatory-page-1"
    chunk = DocumentWithEmbedding(
        content=text,
        id_=chunk_id,
        embedding=[1.0, 0.0, 0.0],
        metadata={
            "file_id": source_id,
            "file_name": path.name,
            "file_path": str(path),
            "page_label": "1",
            "type": "text",
        },
    )
    index._resources["DocStore"].add([chunk], ids=[chunk_id])
    index._resources["VectorStore"].add([chunk])
    with Session(engine) as session:
        session.add(
            index._resources["Source"](
                id=source_id,
                name=path.name,
                path=str(path),
                size=path.stat().st_size,
                user=user_id,
                note={"tokens": 15},
            )
        )
        session.add(
            index._resources["Index"](
                source_id=source_id,
                target_id=chunk_id,
                relation_type="document",
                user=user_id,
            )
        )
        session.commit()
    return source_id
