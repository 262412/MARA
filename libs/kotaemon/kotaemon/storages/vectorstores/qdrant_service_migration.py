"""Reserve and verify the server-side identity of a migrated namespace."""

import re
from contextlib import closing
from uuid import uuid4

MARKER_COLLECTION = "mara_migration"


def require_server_version(client):
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", client.info().version)
    if match is None or tuple(map(int, match.groups())) < (1, 19, 2):
        raise RuntimeError(
            "MARA requires Qdrant server 1.19.2 or newer for security fixes"
        )


def reserve_namespace(url, api_key, namespace):
    from qdrant_client import QdrantClient, models

    with closing(QdrantClient(url=url, api_key=api_key)) as client:
        require_server_version(client)
        prefix = namespace + "__"
        if any(
            item.name.startswith(prefix)
            for item in client.get_collections().collections
        ):
            raise FileExistsError("Migration requires a new, unused Qdrant namespace")
        client.create_collection(
            prefix + MARKER_COLLECTION,
            vectors_config=models.VectorParams(size=1, distance=models.Distance.EUCLID),
        )


def complete_namespace(url, api_key, namespace):
    from qdrant_client import QdrantClient, models

    identity = str(uuid4())
    with closing(QdrantClient(url=url, api_key=api_key)) as client:
        client.upsert(
            namespace + "__" + MARKER_COLLECTION,
            points=[
                models.PointStruct(
                    id=0, vector=[0.0], payload={"migration_id": identity}
                )
            ],
            wait=True,
        )
    return identity


def require_server_identity(client, namespace, receipt):
    collection = namespace + "__" + MARKER_COLLECTION
    if client.collection_exists(collection):
        records = client.retrieve(collection, ids=[0], with_payload=True)
        if records and records[0].payload.get("migration_id") == receipt.get(
            "migration_id"
        ):
            return
    raise RuntimeError("The Qdrant server does not contain the verified migration")
