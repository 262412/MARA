"""Owned preview files with hostile display metadata, never hostile disk paths."""

import base64
from pathlib import Path


def seed_file_browser_documents(app, root):
    from ktem.db.models import User, engine
    from PIL import Image
    from sqlmodel import Session, select

    from kotaemon.base import DocumentWithEmbedding

    index = app.chat_page.file_index
    with Session(engine) as session:
        for username in ("browser-owner", "browser-other"):
            user = session.exec(select(User).where(User.username == username)).one()
            for kind in ("text", "image"):
                source_id = f"r3c-{username}-{kind}"
                suffix = ".txt" if kind == "text" else ".png"
                path = Path(index._resources["FileStoragePath"]) / (source_id + suffix)
                assert path.resolve().is_relative_to(root)
                name = (
                    f"{username} Ω & <img src='/r3c-exfil' "
                    "onerror='globalThis.r3cInjected=1'>" + suffix
                )
                text = f"{username} ALPHA Ω & <b>literal</b> '\" a.b\n" * 120
                if kind == "text":
                    path.write_text(text, encoding="utf-8")
                else:
                    Image.new("RGB", (24, 24), color="navy").save(path)
                chunk_id = source_id + "-page-1"
                chunk = DocumentWithEmbedding(
                    content=text if kind == "text" else text[:200],
                    id_=chunk_id,
                    embedding=[1.0, 0.0, 0.0],
                    metadata={
                        "file_id": source_id,
                        "file_name": name,
                        "file_path": str(path),
                        "page_label": "1",
                        "type": "text",
                    },
                )
                index._resources["DocStore"].add([chunk], ids=[chunk_id])
                index._resources["VectorStore"].add([chunk])
                session.add(
                    index._resources["Source"](
                        id=source_id,
                        name=name,
                        path=str(path),
                        size=path.stat().st_size,
                        user=user.id,
                        note={"tokens": 20},
                    )
                )
                session.add(
                    index._resources["Index"](
                        source_id=source_id,
                        target_id=chunk_id,
                        relation_type="document",
                        user=user.id,
                    )
                )
                if kind == "image":
                    seed_thumbnail(index, session, user.id, source_id, name, path)
        session.commit()


def seed_thumbnail(index, session, user_id, source_id, name, path):
    from kotaemon.base import Document

    thumbnail_id = source_id + "-thumbnail"
    thumbnail = Document(
        content="Owned image thumbnail",
        id_=thumbnail_id,
        metadata={
            "type": "thumbnail",
            "page_label": "1",
            "file_id": source_id,
            "file_name": name,
            "image_origin": "data:image/png;base64,"
            + base64.b64encode(path.read_bytes()).decode("ascii"),
        },
    )
    index._resources["DocStore"].add([thumbnail], ids=[thumbnail_id])
    session.add(
        index._resources["Index"](
            source_id=source_id,
            target_id=thumbnail_id,
            relation_type="document",
            user=user_id,
        )
    )
