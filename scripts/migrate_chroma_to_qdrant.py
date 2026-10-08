"""Export an offline legacy Chroma copy, then import/verify in the new runtime."""

import argparse
import importlib.metadata
import importlib.util
import json
import math
import os
import shutil
from pathlib import Path


def _migration_module():
    path = Path(__file__).resolve().parents[1] / (
        "libs/kotaemon/kotaemon/storages/vectorstores/migration.py"
    )
    spec = importlib.util.spec_from_file_location("mara_vector_migration", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load migration implementation: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_snapshot(source, snapshot, output, migration):
    if not (source / "chroma.sqlite3").is_file():
        raise ValueError("Source is not a Chroma persistence directory")
    paths = [source, snapshot, output]
    for left in paths:
        for right in paths:
            if left != right and left.is_relative_to(right):
                raise ValueError(
                    "Source, snapshot and export directories must be disjoint"
                )
    if len(set(paths)) != 3 or snapshot.exists() or output.exists():
        raise FileExistsError("Snapshot and export must both be new directories")
    source_files = migration.tree_hashes(source)
    shutil.copytree(source, snapshot, symlinks=True)
    if source_files != migration.tree_hashes(snapshot):
        raise ValueError("Snapshot does not match source")
    if source_files != migration.tree_hashes(source):
        raise ValueError("Source changed during snapshot; stop MARA before exporting")
    return source_files


def _export_collection(collection, stream):
    count, dimension = collection.count(), 0
    probes: list[dict] = []
    metric = (collection.metadata or {}).get("hnsw:space", "l2")
    if metric != "l2":
        raise ValueError(
            f"Collection {collection.name!r} uses unsupported metric {metric!r}"
        )
    for offset in range(0, count, 128):
        rows = collection.get(
            limit=128, offset=offset, include=["embeddings", "metadatas", "documents"]
        )
        for identifier, vector, metadata, document in zip(
            rows["ids"], rows["embeddings"], rows["metadatas"], rows["documents"]
        ):
            vector = vector.tolist()
            dimension = dimension or len(vector)
            row = {
                "collection": collection.name,
                "id": identifier,
                "embedding": vector,
                "metadata": metadata,
                "document": document,
            }
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            if len(probes) < 3:
                result = collection.query(
                    query_embeddings=[vector], n_results=min(10, count)
                )
                probes.append(
                    {
                        "embedding": vector,
                        "ids": result["ids"][0],
                        "scores": [
                            math.exp(-distance) for distance in result["distances"][0]
                        ],
                    }
                )
    return {
        "name": collection.name,
        "count": count,
        "dimension": dimension,
        "metric": metric,
        "probes": probes,
    }


def export_snapshot(source, snapshot, output):
    version = importlib.metadata.version("chromadb")
    if version not in {"0.5.16", "0.5.17"}:
        raise ValueError(
            f"Use the legacy Chroma 0.5.16/0.5.17 environment, got {version}"
        )
    import chromadb
    from chromadb.config import Settings

    migration = _migration_module()
    source, snapshot, output = (
        Path(path).resolve() for path in (source, snapshot, output)
    )
    source_files = _copy_snapshot(source, snapshot, output, migration)
    output.mkdir(parents=True)
    client = chromadb.PersistentClient(
        path=str(snapshot), settings=Settings(anonymized_telemetry=False)
    )
    try:
        collections = []
        with (output / "records.jsonl").open("x", encoding="utf-8") as stream:
            for item in sorted(client.list_collections(), key=lambda item: item.name):
                collection = client.get_collection(item.name, embedding_function=None)
                collections.append(_export_collection(collection, stream))
    finally:
        client._system.stop()
        from chromadb.api.shared_system_client import SharedSystemClient

        if (
            SharedSystemClient._identifier_to_system.get(client._identifier)
            is client._system
        ):
            del SharedSystemClient._identifier_to_system[client._identifier]
    if source_files != migration.tree_hashes(source):
        raise ValueError(
            "Source changed during export; stop MARA and export a new snapshot"
        )
    manifest = {
        "format": 1,
        "source": str(source),
        "source_files": source_files,
        "chroma_version": version,
        "collections": collections,
        "records_sha256": migration.file_sha256(output / "records.jsonl"),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return {
        "collections": len(collections),
        "points": sum(item["count"] for item in collections),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser(
        "export", help="Run in the old Chroma environment after stopping MARA"
    )
    export.add_argument("--source", type=Path, required=True)
    export.add_argument("--snapshot", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--source-stopped", action="store_true", required=True)
    for name in ("import", "verify"):
        command = commands.add_parser(name, help="Run in the new MARA environment")
        command.add_argument("--export", type=Path, required=True)
        command.add_argument("--target", type=Path, required=True)
        command.add_argument("--url", default=os.environ.get("MARA_QDRANT_URL"))
        command.add_argument(
            "--namespace", default=os.environ.get("MARA_QDRANT_NAMESPACE")
        )
    args = parser.parse_args(argv)
    if args.command == "export":
        result = export_snapshot(args.source, args.snapshot, args.output)
    else:
        from kotaemon.storages.vectorstores.migration import (
            import_snapshot,
            verify_snapshot,
        )

        action = import_snapshot if args.command == "import" else verify_snapshot
        result = action(
            args.export,
            args.target,
            url=args.url,
            namespace=args.namespace,
            api_key=os.environ.get("MARA_QDRANT_API_KEY"),
        )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
