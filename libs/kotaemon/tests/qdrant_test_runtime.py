"""Own local Qdrant collection leases within a test directory."""

import os
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.parse import urlsplit


def service_options(root):
    from kotaemon.storages.vectorstores.migration import default_namespace

    url = os.environ.get("MARA_TEST_QDRANT_URL")
    if not url:
        return None
    if urlsplit(url).hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Qdrant test fixtures require an owned loopback service")
    return {
        "url": url,
        "api_key": os.environ.get("MARA_TEST_QDRANT_API_KEY"),
        "namespace": default_namespace(root),
    }


def clear_service_namespace(root):
    from qdrant_client import QdrantClient

    options = service_options(root)
    if options is None:
        return
    prefix = options["namespace"] + "__"
    with closing(
        QdrantClient(url=options["url"], api_key=options["api_key"])
    ) as client:
        for collection in client.get_collections().collections:
            if collection.name.startswith(prefix):
                client.delete_collection(collection.name)


@contextmanager
def owned_qdrant_stores(root, *, cleanup=False):
    from kotaemon.storages import QdrantVectorStore

    stores = []
    directories = set()

    def create(path=None, collection_name="default", **kwargs):
        directory = Path(path or root / "qdrant").resolve()
        if not directory.is_relative_to(Path(root).resolve()):
            raise ValueError("Qdrant fixture path must stay inside its owned directory")
        options = service_options(directory)
        config: dict = {"path": str(directory)}
        if options:
            config = {**options, "mara_compatibility": True}
            directories.add(directory)
        store = QdrantVectorStore(collection_name=collection_name, **config, **kwargs)
        stores.append(store)
        return store

    try:
        yield create
    finally:
        for store in reversed(stores):
            store.close()
        if cleanup:
            for directory in directories:
                clear_service_namespace(directory)
