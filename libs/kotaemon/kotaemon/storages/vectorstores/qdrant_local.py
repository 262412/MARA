"""Ownership of local Qdrant clients shared by collections in one process."""

import json
import os
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid5

_CLIENTS = {}
_CLIENTS_LOCK = RLock()
_ID_NAMESPACE = UUID("016b10bc-36e5-5c04-a7b1-7b3b7c0c6837")


class LocalClient:
    def __init__(self, path):
        from qdrant_client import QdrantClient

        self.client = QdrantClient(path=path, force_disable_check_same_thread=True)
        self.lock = RLock()
        self.owners = 0


def acquire_local_client(path):
    path = str(Path(path).resolve())
    key = os.path.normcase(path)
    with _CLIENTS_LOCK:
        if key not in _CLIENTS:
            _CLIENTS[key] = LocalClient(path)
        state = _CLIENTS[key]
        state.owners += 1
        return path, state


def release_local_client(path, state):
    with _CLIENTS_LOCK, state.lock:
        state.owners -= 1
        if state.owners == 0:
            try:
                state.client.close()
            finally:
                del _CLIENTS[os.path.normcase(path)]


def point_id(identifier):
    """Encode every external ID, including UUID-looking strings, in one namespace."""
    return str(uuid5(_ID_NAMESPACE, identifier))


def local_vector_store_class():
    from llama_index.vector_stores.qdrant import QdrantVectorStore

    class LocalVectorStore(QdrantVectorStore):
        def _build_points(self, nodes, sparse_vector_name):
            points, ids = super()._build_points(nodes, sparse_vector_name)
            for point in points:
                point.id = point_id(str(point.id))
            return points, ids

        def parse_to_query_result(self, response):
            from kotaemon.base import DocumentWithEmbedding

            result = super().parse_to_query_result(response)
            for index, point in enumerate(response):
                node = DocumentWithEmbedding.model_validate(
                    json.loads(point.payload["_node_content"])
                )
                node.embedding = result.nodes[index].embedding
                result.nodes[index] = node
            result.ids = [node.node_id for node in result.nodes]
            return result

    return LocalVectorStore
