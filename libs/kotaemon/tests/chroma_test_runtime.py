"""Own the Chroma systems created by one fixture, including their native files."""

from contextlib import contextmanager
from pathlib import Path


@contextmanager
def owned_chroma_stores(root: Path):
    from chromadb.api.shared_system_client import SharedSystemClient

    from kotaemon.storages import ChromaVectorStore

    root = root.resolve()
    systems = {}

    def create(*, path=None, **kwargs):
        directory = Path(path or root / "chroma").resolve()
        if not directory.is_relative_to(root):
            raise ValueError("Chroma fixture path must stay inside its owned directory")
        identifier = str(directory)
        registry = SharedSystemClient._identifier_to_system
        if identifier in registry and identifier not in systems:
            raise ValueError("Chroma system is already owned by another instance")
        store = ChromaVectorStore(path=identifier, **kwargs)
        systems[identifier] = registry[identifier]
        return store

    try:
        yield create
    finally:
        for identifier, system in systems.items():
            # Chroma System.stop closes each persistent HNSW index and DB pool.
            # Several clients created by this fixture can share this system.
            system.stop()
            registry = SharedSystemClient._identifier_to_system
            if registry.get(identifier) is system:
                del registry[identifier]
