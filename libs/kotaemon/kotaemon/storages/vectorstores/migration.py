"""Verified import of an offline Chroma snapshot into a new Qdrant store."""

import hashlib
import json
import math
import os
import stat
from contextlib import ExitStack
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_hashes(root):
    root = Path(root).resolve()
    hashes = {}
    for entry in sorted(root.rglob("*")):
        info = entry.lstat()
        if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(
                f"Snapshot source contains a link or reparse point: {entry}"
            )
        if stat.S_ISREG(info.st_mode):
            hashes[entry.relative_to(root).as_posix()] = file_sha256(entry)
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"Snapshot source contains a non-regular file: {entry}")
    return hashes


def default_namespace(user_data_dir):
    identity = os.path.normcase(str(Path(user_data_dir).resolve()))
    return "mara_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def configured_vectorstore(user_data_dir, read_config):
    return default_vectorstore(
        user_data_dir,
        url=read_config("MARA_QDRANT_URL", default="http://127.0.0.1:6333"),
        api_key=read_config("MARA_QDRANT_API_KEY", default=None),
        namespace=read_config("MARA_QDRANT_NAMESPACE", default=None),
    )


def default_vectorstore(
    user_data_dir, *, url="http://127.0.0.1:6333", api_key=None, namespace=None
):
    root = Path(user_data_dir)
    return {
        "__type__": "kotaemon.storages.QdrantVectorStore",
        "url": url,
        "api_key": api_key,
        "namespace": namespace or default_namespace(root),
        "mara_compatibility": True,
        "migration_path": str(root / "vectorstore_qdrant"),
        "legacy_path": str(root / "vectorstore"),
    }


def require_verified_migration(legacy, target, *, url=None, namespace=None):
    if target is None:
        raise ValueError("A migration receipt directory is required for legacy data")
    legacy, target = Path(legacy), Path(target)
    if (target / "mara-import-in-progress.json").exists():
        raise RuntimeError(
            "Qdrant migration is incomplete; use a new target and rerun import"
        )
    if (legacy / "chroma.sqlite3").exists():
        marker = target / "mara-migration.json"
        message = (
            "Existing Chroma data requires verified migration. Stop MARA and run "
            "scripts/migrate_chroma_to_qdrant.py; see docs/development/data-components.md."
        )
        if not marker.is_file() or (
            url is None and not (target / "meta.json").is_file()
        ):
            raise RuntimeError(message)
        try:
            receipt = json.loads(marker.read_text(encoding="utf-8"))
            ready = (
                receipt["format"] == 1
                and receipt["status"] == "verified"
                and Path(receipt["source"]).resolve() == legacy.resolve()
                and receipt["source_files"] == tree_hashes(legacy)
                and receipt.get("destination") == _destination(url, namespace)
                and (url is None or isinstance(receipt.get("migration_id"), str))
            )
        except (ValueError, KeyError, TypeError, OSError) as error:
            raise RuntimeError(message) from error
        if not ready:
            raise RuntimeError("Legacy source changed after migration. " + message)
        return receipt
    return None


def _destination(url, namespace):
    if url is None:
        if namespace is not None:
            raise ValueError("A Qdrant namespace requires a service URL")
        return None
    validate_collection_name(namespace)
    if "__" in namespace:
        raise ValueError("Qdrant namespace cannot contain '__'")
    return {"url": url.rstrip("/"), "namespace": namespace}


def validate_collection_name(name):
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or any(character in name for character in '/\\\x00<>:"|?*')
        or name.rstrip(". ") != name
    ):
        raise ValueError(f"Unsupported collection name: {name!r}")


def _load_manifest(export):
    manifest = json.loads((export / "manifest.json").read_text(encoding="utf-8"))
    if manifest["format"] != 1:
        raise ValueError("Unsupported Chroma export format")
    if file_sha256(export / "records.jsonl") != manifest["records_sha256"]:
        raise ValueError("Chroma export records hash mismatch")
    collections = manifest["collections"]
    names = set()
    for collection in collections:
        name = collection["name"]
        validate_collection_name(name)
        if name == "mara_migration":
            raise ValueError("Collection name is reserved for migration identity")
        if name.casefold() in names:
            raise ValueError("Duplicate or case-colliding collection names")
        names.add(name.casefold())
        if collection["metric"] != "l2":
            raise ValueError("Only Chroma L2 collections can use this migration")
        if collection["count"] < 0 or collection["dimension"] < 0:
            raise ValueError("Invalid collection count or dimension")
    return manifest


def _read_documents(export):
    from kotaemon.base import DocumentWithEmbedding

    with (export / "records.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            metadata = row["metadata"]
            if not metadata or "_node_content" not in metadata:
                raise ValueError("Export contains a non-MARA Chroma record")
            doc = DocumentWithEmbedding.model_validate(
                json.loads(metadata["_node_content"])
            )
            if not isinstance(row["id"], str) or not row["id"] or doc.id_ != row["id"]:
                raise ValueError("Export ID does not match the serialized document")
            doc.embedding = row["embedding"]
            if row["document"] is not None:
                doc.text = row["document"]
            yield row["collection"], doc


def _preflight(export, manifest):
    collections = {item["name"]: item for item in manifest["collections"]}
    seen: dict[str, set[str]] = {name: set() for name in collections}
    for name, doc in _read_documents(export):
        if name not in collections:
            raise ValueError("Export record names an undeclared collection")
        if doc.id_ in seen[name]:
            raise ValueError("Export contains a duplicate document ID")
        seen[name].add(doc.id_)
        if not doc.embedding or len(doc.embedding) != collections[name]["dimension"]:
            raise ValueError("Export vector dimension mismatch")
        if not all(math.isfinite(value) for value in doc.embedding):
            raise ValueError("Export contains a non-finite vector")
    for name, collection in collections.items():
        if len(seen[name]) != collection["count"]:
            raise ValueError("Export collection count mismatch")


def _open_stores(target, manifest, stack, *, url=None, api_key=None, namespace=None):
    from .qdrant import QdrantVectorStore

    stores = {}
    for item in manifest["collections"]:
        config = (
            {"path": target}
            if url is None
            else {
                "url": url,
                "api_key": api_key,
                "namespace": namespace,
                "mara_compatibility": True,
            }
        )
        store = QdrantVectorStore(collection_name=item["name"], **config)
        stack.callback(store.close)
        stores[item["name"]] = store
    return stores


def _verify_document(actual, expected):
    if actual.model_dump(exclude={"embedding", "class_name"}) != expected.model_dump(
        exclude={"embedding", "class_name"}
    ):
        raise ValueError(f"Migrated document payload mismatch: {expected.id_}")
    if len(actual.embedding) != len(expected.embedding) or any(
        not math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-7)
        for a, b in zip(actual.embedding, expected.embedding)
    ):
        raise ValueError(f"Migrated document vector mismatch: {expected.id_}")


def _document_batches(export, size=128):
    name = None
    batch: list = []
    for collection, doc in _read_documents(export):
        if batch and (collection != name or len(batch) == size):
            yield name, batch
            batch = []
        name = collection
        batch.append(doc)
    if batch:
        yield name, batch


def _verify_batch(store, batch):
    from .qdrant_local import point_id

    points = store._client.client.retrieve(
        store._collection_name,
        ids=[point_id(doc.id_) for doc in batch],
        with_payload=True,
        with_vectors=True,
    )
    nodes = store._client.parse_to_query_result(points).nodes
    actual = {node.id_: node for node in nodes}
    for expected in batch:
        if expected.id_ not in actual:
            raise ValueError(f"Migrated document is missing: {expected.id_}")
        _verify_document(actual[expected.id_], expected)


def verify_snapshot(export, target, *, url=None, api_key=None, namespace=None):
    export, target = Path(export).resolve(), Path(target).resolve()
    if not target.is_dir() or (url is None and not (target / "meta.json").is_file()):
        raise ValueError("Qdrant target is missing")
    if url is not None:
        marker = target / "mara-migration.json"
        if not marker.exists():
            marker = target / "mara-import-in-progress.json"
        binding = json.loads(marker.read_text(encoding="utf-8"))
        if binding.get("destination") != _destination(url, namespace):
            raise ValueError(
                "Migration receipt belongs to a different Qdrant destination"
            )
    manifest = _load_manifest(export)
    _preflight(export, manifest)
    with ExitStack() as stack:
        stores = _open_stores(
            target, manifest, stack, url=url, api_key=api_key, namespace=namespace
        )
        for collection in manifest["collections"]:
            store = stores[collection["name"]]
            if store.count() != collection["count"]:
                raise ValueError(
                    f"Migrated collection count mismatch: {collection['name']}"
                )
            for probe in collection.get("probes", []):
                _, scores, ids = store.query(
                    probe["embedding"], top_k=len(probe["ids"])
                )
                if len(scores) != len(probe["scores"]) or any(
                    not math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-7)
                    for a, b in zip(scores, probe["scores"])
                ):
                    raise ValueError("Migrated nearest-neighbor scores differ")
                if len(set(probe["scores"])) == len(scores) and ids != probe["ids"]:
                    raise ValueError("Migrated nearest-neighbor ordering differs")
        for name, batch in _document_batches(export):
            _verify_batch(stores[name], batch)
    return {
        "collections": len(manifest["collections"]),
        "points": sum(item["count"] for item in manifest["collections"]),
    }


def import_snapshot(export, target, *, url=None, api_key=None, namespace=None):
    export, target = Path(export).resolve(), Path(target).resolve()
    if target.exists():
        raise FileExistsError("Migration target must be a new directory")
    manifest = _load_manifest(export)
    manifest_hash = file_sha256(export / "manifest.json")
    _preflight(export, manifest)
    destination = _destination(url, namespace)
    if file_sha256(export / "records.jsonl") != manifest["records_sha256"]:
        raise ValueError("Export changed during preflight")
    if url is not None:
        from .qdrant_service_migration import reserve_namespace

        reserve_namespace(url, api_key, namespace)
    target.mkdir(parents=True)
    in_progress = target / "mara-import-in-progress.json"
    in_progress.write_text(
        json.dumps({"export": str(export), "destination": destination}),
        encoding="utf-8",
    )
    with ExitStack() as stack:
        if url is None:
            from .qdrant_local import acquire_local_client, release_local_client

            path, state = acquire_local_client(target)
            stack.callback(release_local_client, path, state)
        stores = _open_stores(
            target, manifest, stack, url=url, api_key=api_key, namespace=namespace
        )
        for name, batch in _document_batches(export):
            stores[name].add(batch)
    options = {"url": url, "api_key": api_key, "namespace": namespace}
    result = (
        verify_snapshot(export, target, **options)
        if url
        else verify_snapshot(export, target)
    )
    if (
        file_sha256(export / "manifest.json") != manifest_hash
        or file_sha256(export / "records.jsonl") != manifest["records_sha256"]
    ):
        raise ValueError("Export changed during migration")
    marker = {
        "format": 1,
        "status": "verified",
        "source": manifest["source"],
        "source_files": manifest["source_files"],
        "records_sha256": manifest["records_sha256"],
        "probe_sources": {
            item["name"]: item.get("probe_source", "chroma")
            for item in manifest["collections"]
        },
        "destination": destination,
        **result,
    }
    if url is not None:
        from .qdrant_service_migration import complete_namespace

        marker["migration_id"] = complete_namespace(url, api_key, namespace)
    marker_path = target / "mara-migration.json"
    temporary = marker_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    temporary.replace(marker_path)
    in_progress.unlink()
    return result
